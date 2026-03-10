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
from .models import ApplicableRate, SolarEstimate, TariffCostComparison

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

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parse an ISO datetime string."""
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async def get_applicable_rates(
        self,
        account_number: str,
        mpxn: str,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[ApplicableRate]:
        """Get actual rates applied to a meter.

        Uses Relay pagination (edges/nodes) internally.

        Args:
            account_number: Octopus Energy account number.
            mpxn: MPAN or MPRN.
            start_at: Start of period.
            end_at: End of period.

        Returns:
            Flat list of applicable rates.
        """
        query = """
        query applicableRates(
            $accountNumber: String!,
            $mpxn: String!,
            $startAt: DateTime!,
            $endAt: DateTime!,
            $cursor: String
        ) {
          applicableRates(
            accountNumber: $accountNumber,
            mpxn: $mpxn,
            startAt: $startAt,
            endAt: $endAt,
            after: $cursor
          ) {
            edges {
              node {
                valueIncVat
                validFrom
                validTo
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        all_rates: list[ApplicableRate] = []
        cursor: str | None = None

        while True:
            variables: dict[str, Any] = {
                "accountNumber": account_number,
                "mpxn": mpxn,
                "startAt": start_at.isoformat(),
                "endAt": end_at.isoformat(),
            }
            if cursor:
                variables["cursor"] = cursor

            data = await self._execute(query, variables=variables)
            rates_data = data["applicableRates"]

            for edge in rates_data.get("edges", []):
                node = edge["node"]
                all_rates.append(
                    ApplicableRate(
                        value_inc_vat=node["valueIncVat"],
                        valid_from=self._parse_datetime(node["validFrom"]),
                        valid_to=self._parse_datetime(node["validTo"]),
                    )
                )

            page_info = rates_data.get("pageInfo", {})
            if page_info.get("hasNextPage"):
                cursor = page_info["endCursor"]
            else:
                break

        return all_rates

    async def get_solar_generation_estimate(
        self,
        postcode: str,
        *,
        from_date: datetime | None = None,
    ) -> list[SolarEstimate]:
        """Get hourly solar generation estimates for a postcode.

        Args:
            postcode: UK postcode.
            from_date: Start date for estimates. Defaults to today.

        Returns:
            List of hourly solar generation estimates in kWh.
        """
        query = """
        query getSolarEstimate($postcode: String!, $fromDate: Date!) {
          getSolarGenerationEstimate(postcode: $postcode, fromDate: $fromDate) {
            solarGenerationEstimates {
              date
              hour
              value
            }
          }
        }
        """
        date_str = (from_date or datetime.now(UTC)).strftime("%Y-%m-%d")
        variables: dict[str, Any] = {"postcode": postcode, "fromDate": date_str}

        data = await self._execute(query, variables=variables)
        container = data.get("getSolarGenerationEstimate") or {}
        return [
            SolarEstimate(
                date=item["date"],
                hour=item["hour"],
                value=item["value"],
            )
            for item in container.get("solarGenerationEstimates", [])
        ]

    async def get_smart_tariff_comparison(
        self,
        *,
        account_number: str,
        mpan: str | None = None,
    ) -> dict:
        """Get tariff cost comparison from Octopus.

        Args:
            account_number: Octopus Energy account number.
            mpan: Optional MPAN to compare for.

        Returns:
            Dict with 'current_cost' and 'comparisons' list.
        """
        query = """
        query smartTariffComparison(
            $accountNumber: String!,
            $mpan: String
        ) {
          smartTariffComparison(
            accountNumber: $accountNumber,
            mpan: $mpan
          ) {
            currentCost
            comparisons {
              tariffCode
              productCode
              costIncVat
            }
          }
        }
        """
        variables: dict[str, Any] = {"accountNumber": account_number}
        if mpan:
            variables["mpan"] = mpan

        data = await self._execute(query, variables=variables)
        result = data["smartTariffComparison"]

        comparisons = [
            TariffCostComparison(
                tariff_code=c["tariffCode"],
                product_code=c["productCode"],
                cost_inc_vat=c["costIncVat"],
            )
            for c in result.get("comparisons", [])
        ]

        return {
            "current_cost": result.get("currentCost"),
            "comparisons": comparisons,
        }
