"""Async GraphQL client for the Octopus Energy API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Self

import aiohttp

from .const import GRAPHQL_URL
from .exceptions import (
    OctopusEnergyAuthenticationError,
    OctopusEnergyConnectionError,
    OctopusEnergyError,
    OctopusEnergyTimeoutError,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

_OBTAIN_TOKEN_MUTATION = """
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
    refreshToken
    refreshExpiresIn
  }
}
"""

# Refresh buffer: refresh token 5 minutes before expiry
_TOKEN_REFRESH_BUFFER = timedelta(minutes=5)
# Default token lifetime if not otherwise known (Kraken tokens ~60 min)
_DEFAULT_TOKEN_LIFETIME = timedelta(minutes=55)


class OctopusEnergyGraphQLClient:
    """Async GraphQL client for the Octopus Energy Kraken API.

    Uses JWT authentication obtained via API key. Can share an aiohttp
    session with the REST client.
    """

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the GraphQL client."""
        self._api_key = api_key
        self._session = session
        self._owns_session = session is None

        self._token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: datetime | None = None

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        if self._owns_session:
            self._session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def _ensure_token(self) -> str:
        """Obtain or refresh JWT token as needed."""
        now = datetime.now(UTC)

        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        if self._refresh_token:
            try:
                await self._refresh_auth()
                return self._token  # type: ignore[return-value]
            except OctopusEnergyError:
                pass

        await self._obtain_token()
        return self._token  # type: ignore[return-value]

    async def _obtain_token(self) -> None:
        """Obtain a new JWT token using the API key."""
        data = await self._execute(
            _OBTAIN_TOKEN_MUTATION,
            variables={"input": {"APIKey": self._api_key}},
            auth=False,
        )
        result = data["obtainKrakenToken"]
        self._token = result["token"]
        self._refresh_token = result.get("refreshToken")
        self._token_expiry = datetime.now(UTC) + _DEFAULT_TOKEN_LIFETIME

    async def _refresh_auth(self) -> None:
        """Refresh the JWT token using the refresh token."""
        data = await self._execute(
            _OBTAIN_TOKEN_MUTATION,
            variables={"input": {"refreshToken": self._refresh_token}},
            auth=False,
        )
        result = data["obtainKrakenToken"]
        self._token = result["token"]
        self._refresh_token = result.get("refreshToken")
        self._token_expiry = datetime.now(UTC) + _DEFAULT_TOKEN_LIFETIME

    async def _execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        auth: bool = True,
    ) -> dict:
        """Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query string.
            variables: Query variables.
            auth: Whether to include JWT auth header.

        Returns:
            The 'data' portion of the GraphQL response.

        Raises:
            OctopusEnergyError: On GraphQL errors or HTTP errors.
        """
        if self._session is None:
            msg = "Session not initialized. Use as context manager or pass a session."
            raise OctopusEnergyError(msg)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth:
            token = await self._ensure_token()
            headers["Authorization"] = f"JWT {token}"

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            async with self._session.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    msg = "Invalid API key"
                    raise OctopusEnergyAuthenticationError(msg)
                if resp.status != 200:
                    msg = f"GraphQL API returned status {resp.status}"
                    raise OctopusEnergyError(msg)

                body = await resp.json()

                if "errors" in body:
                    errors = body["errors"]
                    messages = [e.get("message", str(e)) for e in errors]
                    if any("authentication" in m.lower() for m in messages):
                        raise OctopusEnergyAuthenticationError(
                            "; ".join(messages)
                        )
                    msg = f"GraphQL errors: {'; '.join(messages)}"
                    raise OctopusEnergyError(msg)

                return body.get("data", {})

        except (OctopusEnergyAuthenticationError, OctopusEnergyError):
            raise
        except TimeoutError as err:
            msg = f"Timeout connecting to {GRAPHQL_URL}"
            raise OctopusEnergyTimeoutError(msg) from err
        except aiohttp.ClientError as err:
            msg = f"Error connecting to {GRAPHQL_URL}"
            raise OctopusEnergyConnectionError(msg) from err
