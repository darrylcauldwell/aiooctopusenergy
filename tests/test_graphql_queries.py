"""Tests for GraphQL query methods."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from aiooctopusenergy import (
    ApplicableRate,
    OctopusEnergyGraphQLClient,
    SmartMeterDevice,
    SmartMeterTelemetry,
    SolarEstimate,
    TariffCostComparison,
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
                "token": "jwt-test-token",
                "refreshToken": "refresh-token",
                "refreshExpiresIn": 604800,
            }
        }
    }


class TestGetApplicableRates:
    @pytest.mark.asyncio
    async def test_success(
        self,
        mock_session,
        token_response,
        applicable_rates_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(applicable_rates_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_applicable_rates(
            "A-AAAA1111",
            "1100009640372",
            start_at=datetime(2026, 3, 6, 21, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 6, 23, 0, tzinfo=UTC),
        )

        assert len(result) == 3
        assert all(isinstance(r, ApplicableRate) for r in result)
        assert result[0].value_inc_vat == 20.517
        assert result[0].valid_from == datetime(2026, 3, 6, 22, 30, tzinfo=UTC)
        assert result[0].valid_to == datetime(2026, 3, 6, 23, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_relay_pagination(
        self,
        mock_session,
        token_response,
        applicable_rates_paginated_response,
        applicable_rates_page2_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(applicable_rates_paginated_response),
                _mock_post_response(applicable_rates_page2_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_applicable_rates(
            "A-AAAA1111",
            "1100009640372",
            start_at=datetime(2026, 3, 6, 20, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 6, 22, 0, tzinfo=UTC),
        )

        assert len(result) == 2
        assert result[0].value_inc_vat == 18.50
        assert result[1].value_inc_vat == 19.25
        # 3 posts: token + page1 + page2
        assert mock_session.post.call_count == 3

        # Verify cursor was passed in second query
        second_query_call = mock_session.post.call_args_list[2]
        variables = second_query_call.kwargs["json"]["variables"]
        assert variables["cursor"] == "cursor-page-1"


class TestGetSolarGenerationEstimate:
    @pytest.mark.asyncio
    async def test_success(
        self,
        mock_session,
        token_response,
        solar_estimate_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(solar_estimate_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_solar_generation_estimate("DE45 1AB")

        assert len(result) == 9
        assert all(isinstance(e, SolarEstimate) for e in result)
        assert result[0].date == "2026-03-06"
        assert result[0].hour == 8
        assert result[0].value == 0.12
        assert result[4].hour == 12
        assert result[4].value == 0.85

    @pytest.mark.asyncio
    async def test_with_from_date(
        self,
        mock_session,
        token_response,
        solar_estimate_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(solar_estimate_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        from_date = datetime(2026, 3, 6, tzinfo=UTC)
        await client.get_solar_generation_estimate("DE45 1AB", from_date=from_date)

        query_call = mock_session.post.call_args_list[1]
        variables = query_call.kwargs["json"]["variables"]
        assert "fromDate" in variables

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_session, token_response):
        empty = {"data": {"getSolarGenerationEstimate": {"solarGenerationEstimates": []}}}
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(empty),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_solar_generation_estimate("XX1 1XX")
        assert result == []


class TestGetSmartTariffComparison:
    @pytest.mark.asyncio
    async def test_success(
        self,
        mock_session,
        token_response,
        tariff_comparison_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(tariff_comparison_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_smart_tariff_comparison(
            account_number="A-AAAA1111"
        )

        assert result["current_cost"] == 125.50
        comparisons = result["comparisons"]
        assert len(comparisons) == 3
        assert all(isinstance(c, TariffCostComparison) for c in comparisons)

        cheapest = comparisons[1]
        assert cheapest.tariff_code == "E-1R-GO-VAR-22-10-14-C"
        assert cheapest.product_code == "GO-VAR-22-10-14"
        assert cheapest.cost_inc_vat == 98.75

    @pytest.mark.asyncio
    async def test_with_mpan(
        self,
        mock_session,
        token_response,
        tariff_comparison_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(tariff_comparison_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        await client.get_smart_tariff_comparison(
            account_number="A-AAAA1111", mpan="1100009640372"
        )

        query_call = mock_session.post.call_args_list[1]
        variables = query_call.kwargs["json"]["variables"]
        assert variables["mpan"] == "1100009640372"


class TestGetSmartMeterDevices:
    @pytest.mark.asyncio
    async def test_success_skips_meters_without_a_smart_device(
        self,
        mock_session,
        token_response,
        smart_meter_devices_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(smart_meter_devices_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_smart_meter_devices("A-AAAA1111")

        assert result == [
            SmartMeterDevice(
                mpan="1100009640372",
                serial_number="22L4344979",
                device_id="00-11-22-33-44-55-66-77",
            )
        ]
        variables = mock_session.post.call_args_list[1].kwargs["json"]["variables"]
        assert variables == {"accountNumber": "A-AAAA1111"}

    @pytest.mark.asyncio
    async def test_no_account(self, mock_session, token_response):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response({"data": {"account": None}}),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        assert await client.get_smart_meter_devices("A-AAAA1111") == []


class TestGetSmartMeterTelemetry:
    @pytest.mark.asyncio
    async def test_success_converts_units(
        self,
        mock_session,
        token_response,
        smart_meter_telemetry_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(smart_meter_telemetry_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_smart_meter_telemetry(
            "00-11-22-33-44-55-66-77",
            start=datetime(2026, 11, 9, 8, 9, tzinfo=UTC),
            end=datetime(2026, 11, 9, 8, 10, tzinfo=UTC),
        )

        assert len(result) == 3
        assert all(isinstance(r, SmartMeterTelemetry) for r in result)
        assert result[1].read_at == datetime(2026, 11, 9, 8, 9, 40, tzinfo=UTC)
        assert result[1].consumption_kwh == pytest.approx(11326.045)
        assert result[1].demand_w == pytest.approx(1843.5)
        assert result[1].consumption_delta_kwh == pytest.approx(0.025)
        assert result[0].demand_w == 0.0

    @pytest.mark.asyncio
    async def test_null_values_become_none(
        self,
        mock_session,
        token_response,
        smart_meter_telemetry_graphql_response,
    ):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response(smart_meter_telemetry_graphql_response),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        result = await client.get_smart_meter_telemetry(
            "00-11-22-33-44-55-66-77",
            start=datetime(2026, 11, 9, 8, 9, tzinfo=UTC),
            end=datetime(2026, 11, 9, 8, 10, tzinfo=UTC),
        )

        assert result[2].consumption_kwh is None
        assert result[2].demand_w is None
        assert result[2].consumption_delta_kwh is None

    @pytest.mark.asyncio
    async def test_grouping_and_window_are_sent(self, mock_session, token_response):
        mock_session.post = MagicMock(
            side_effect=[
                _mock_post_response(token_response),
                _mock_post_response({"data": {"smartMeterTelemetry": None}}),
            ]
        )
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )
        start = datetime(2026, 11, 9, 0, 0, tzinfo=UTC)
        end = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)

        result = await client.get_smart_meter_telemetry(
            "00-11", start=start, end=end, grouping="HALF_HOURLY"
        )

        assert result == []
        payload = mock_session.post.call_args_list[1].kwargs["json"]
        assert payload["variables"] == {
            "deviceId": "00-11",
            "grouping": "HALF_HOURLY",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    @pytest.mark.asyncio
    async def test_unknown_grouping_rejected_before_any_request(self, mock_session):
        mock_session.post = MagicMock()
        client = OctopusEnergyGraphQLClient(
            api_key="sk_live_test", session=mock_session
        )

        with pytest.raises(ValueError):
            await client.get_smart_meter_telemetry(
                "00-11",
                start=datetime(2026, 11, 9, tzinfo=UTC),
                end=datetime(2026, 11, 9, 1, tzinfo=UTC),
                grouping="TEN_MINUTES",
            )
        mock_session.post.assert_not_called()

