"""Tests for OctopusEnergyGraphQLClient."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from aiooctopusenergy import (
    OctopusEnergyAuthenticationError,
    OctopusEnergyConnectionError,
    OctopusEnergyError,
    OctopusEnergyGraphQLClient,
    OctopusEnergyTimeoutError,
)


def _mock_post_response(data: dict, status: int = 200) -> MagicMock:
    """Create a mock aiohttp POST response context manager."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp session."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def token_response() -> dict:
    """Return a successful token obtain response."""
    return {
        "data": {
            "obtainKrakenToken": {
                "token": "jwt-test-token-123",
                "refreshToken": "refresh-test-token-456",
                "refreshExpiresIn": 604800,
            }
        }
    }


@pytest.fixture
def refreshed_token_response() -> dict:
    """Return a successful token refresh response."""
    return {
        "data": {
            "obtainKrakenToken": {
                "token": "jwt-refreshed-token-789",
                "refreshToken": "refresh-new-token-012",
                "refreshExpiresIn": 604800,
            }
        }
    }


class TestObtainToken:
    @pytest.mark.asyncio
    async def test_obtain_token_on_first_request(
        self, mock_session, token_response
    ):
        query_response = {"data": {"someQuery": {"value": 42}}}
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(query_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client._execute("{ someQuery { value } }")

        assert result == {"someQuery": {"value": 42}}
        assert mock_session.post.call_count == 2

        # First call is token obtain
        first_call = mock_session.post.call_args_list[0]
        first_body = first_call.kwargs["json"]
        assert "obtainKrakenToken" in first_body["query"]
        assert first_body["variables"]["input"]["APIKey"] == "sk_live_test"

        # Second call has JWT header
        second_call = mock_session.post.call_args_list[1]
        headers = second_call.kwargs["headers"]
        assert headers["Authorization"] == "JWT jwt-test-token-123"

    @pytest.mark.asyncio
    async def test_reuses_valid_token(self, mock_session, token_response):
        query_response = {"data": {"someQuery": {"value": 1}}}
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(query_response),
                _mock_post_response(query_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        await client._execute("{ query1 }")
        await client._execute("{ query2 }")

        # 1 token obtain + 2 queries = 3 calls
        assert mock_session.post.call_count == 3


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_on_expiry(
        self, mock_session, token_response, refreshed_token_response
    ):
        query_response = {"data": {"someQuery": {"value": 1}}}
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(query_response),
                _mock_post_response(refreshed_token_response),
                _mock_post_response(query_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        # First query: obtain token + execute
        await client._execute("{ query1 }")

        # Expire the token
        client._token_expiry = datetime.now(UTC) - timedelta(minutes=1)

        # Second query: should refresh token
        await client._execute("{ query2 }")

        assert mock_session.post.call_count == 4
        # Third call is refresh
        refresh_call = mock_session.post.call_args_list[2]
        refresh_body = refresh_call.kwargs["json"]
        assert (
            refresh_body["variables"]["input"]["refreshToken"]
            == "refresh-test-token-456"
        )

    @pytest.mark.asyncio
    async def test_fallback_to_obtain_on_refresh_failure(
        self, mock_session, token_response
    ):
        query_response = {"data": {"someQuery": {"value": 1}}}

        # Refresh fails with GraphQL error, then re-obtain succeeds
        refresh_error = {
            "errors": [{"message": "Refresh token expired"}],
        }
        new_token = {
            "data": {
                "obtainKrakenToken": {
                    "token": "jwt-new-token",
                    "refreshToken": "refresh-new",
                    "refreshExpiresIn": 604800,
                }
            }
        }

        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(query_response),
                _mock_post_response(refresh_error),
                _mock_post_response(new_token),
                _mock_post_response(query_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        await client._execute("{ query1 }")
        client._token_expiry = datetime.now(UTC) - timedelta(minutes=1)
        await client._execute("{ query2 }")

        # 5 calls: obtain + query + failed refresh + re-obtain + query
        assert mock_session.post.call_count == 5


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_graphql_errors(self, mock_session, token_response):
        error_response = {
            "errors": [{"message": "Field 'foo' not found"}],
        }
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(error_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        with pytest.raises(OctopusEnergyError, match="GraphQL errors"):
            await client._execute("{ badQuery }")

    @pytest.mark.asyncio
    async def test_authentication_error_in_graphql(
        self, mock_session, token_response
    ):
        error_response = {
            "errors": [{"message": "Authentication required"}],
        }
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(error_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        with pytest.raises(OctopusEnergyAuthenticationError):
            await client._execute("{ protectedQuery }")

    @pytest.mark.asyncio
    async def test_http_401(self, mock_session):
        mock_session.post = MagicMock(
            return_value=_mock_post_response({}, status=401)
        )
        client = OctopusEnergyGraphQLClient(
            api_key="bad_key", session=mock_session
        )

        with pytest.raises(OctopusEnergyAuthenticationError):
            await client._execute("{ query }", auth=False)

    @pytest.mark.asyncio
    async def test_http_500(self, mock_session):
        mock_session.post = MagicMock(
            return_value=_mock_post_response({}, status=500)
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        with pytest.raises(OctopusEnergyError, match="status 500"):
            await client._execute("{ query }", auth=False)

    @pytest.mark.asyncio
    async def test_timeout_error(self, mock_session):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=TimeoutError)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=ctx)
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        with pytest.raises(OctopusEnergyTimeoutError):
            await client._execute("{ query }", auth=False)

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_session):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientConnectionError("Connection refused")
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=ctx)
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        with pytest.raises(OctopusEnergyConnectionError):
            await client._execute("{ query }", auth=False)

    @pytest.mark.asyncio
    async def test_no_session_error(self):
        client = OctopusEnergyGraphQLClient(api_key="sk_live_test")

        with pytest.raises(OctopusEnergyError, match="Session not initialized"):
            await client._execute("{ query }", auth=False)


class TestContextManager:
    @pytest.mark.asyncio
    async def test_creates_and_closes_session(self):
        async with OctopusEnergyGraphQLClient(
            api_key="sk_live_test"
        ) as client:
            assert client._session is not None
        assert client._session is None

    @pytest.mark.asyncio
    async def test_external_session_not_closed(self, mock_session):
        mock_session.close = AsyncMock()
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        await client.close()
        mock_session.close.assert_not_called()
