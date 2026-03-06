"""Tests for day/night rate endpoints and consumption parameters."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from aiooctopusenergy import OctopusEnergyClient


def _mock_response(data: dict, status: int = 200) -> MagicMock:
    """Create a mock aiohttp response context manager."""
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


class TestGetElectricityDayRates:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, day_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(day_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_day_rates(
            "GO-VAR-22-10-14", "E-2R-GO-VAR-22-10-14-C"
        )

        assert len(result) == 2
        assert result[0].value_exc_vat == 28.55
        assert result[0].value_inc_vat == 29.9775
        assert result[0].valid_from == datetime(2026, 3, 6, 5, 30, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_url_path(self, mock_session, day_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(day_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_day_rates(
            "GO-VAR-22-10-14", "E-2R-GO-VAR-22-10-14-C"
        )

        url = mock_session.get.call_args[0][0]
        assert "/electricity-tariffs/E-2R-GO-VAR-22-10-14-C/day-unit-rates/" in url

    @pytest.mark.asyncio
    async def test_no_auth(self, mock_session, day_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(day_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_day_rates(
            "GO-VAR-22-10-14", "E-2R-GO-VAR-22-10-14-C"
        )

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs


class TestGetElectricityNightRates:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, night_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(night_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_night_rates(
            "GO-VAR-22-10-14", "E-2R-GO-VAR-22-10-14-C"
        )

        assert len(result) == 2
        assert result[0].value_exc_vat == 7.5
        assert result[0].value_inc_vat == 7.875
        assert result[0].valid_from == datetime(2026, 3, 6, 0, 30, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_url_path(self, mock_session, night_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(night_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_night_rates(
            "GO-VAR-22-10-14", "E-2R-GO-VAR-22-10-14-C"
        )

        url = mock_session.get.call_args[0][0]
        assert "/electricity-tariffs/E-2R-GO-VAR-22-10-14-C/night-unit-rates/" in url

    @pytest.mark.asyncio
    async def test_no_auth(self, mock_session, night_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(night_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_night_rates(
            "GO-VAR-22-10-14", "E-2R-GO-VAR-22-10-14-C"
        )

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs


class TestGetGasDayRates:
    @pytest.mark.asyncio
    async def test_url_path(self, mock_session, day_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(day_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_gas_day_rates(
            "GO-VAR-22-10-14", "G-2R-GO-VAR-22-10-14-C"
        )

        url = mock_session.get.call_args[0][0]
        assert "/gas-tariffs/G-2R-GO-VAR-22-10-14-C/day-unit-rates/" in url

    @pytest.mark.asyncio
    async def test_no_auth(self, mock_session, day_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(day_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_gas_day_rates(
            "GO-VAR-22-10-14", "G-2R-GO-VAR-22-10-14-C"
        )

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs


class TestGetGasNightRates:
    @pytest.mark.asyncio
    async def test_url_path(self, mock_session, night_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(night_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_gas_night_rates(
            "GO-VAR-22-10-14", "G-2R-GO-VAR-22-10-14-C"
        )

        url = mock_session.get.call_args[0][0]
        assert "/gas-tariffs/G-2R-GO-VAR-22-10-14-C/night-unit-rates/" in url

    @pytest.mark.asyncio
    async def test_no_auth(self, mock_session, night_rates_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(night_rates_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_gas_night_rates(
            "GO-VAR-22-10-14", "G-2R-GO-VAR-22-10-14-C"
        )

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs


class TestConsumptionGroupBy:
    @pytest.mark.asyncio
    async def test_electricity_group_by(self, mock_session, consumption_daily_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_daily_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_consumption(
            "1100009640372", "22L4344979", group_by="day"
        )

        url = mock_session.get.call_args[0][0]
        assert "group_by=day" in url
        assert len(result) == 3
        assert result[0].consumption == 8.456

    @pytest.mark.asyncio
    async def test_electricity_order_by(self, mock_session, consumption_daily_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_daily_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_consumption(
            "1100009640372", "22L4344979", order_by="period"
        )

        url = mock_session.get.call_args[0][0]
        assert "order_by=period" in url

    @pytest.mark.asyncio
    async def test_gas_group_by_and_order_by(
        self, mock_session, consumption_daily_response
    ):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_daily_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_gas_consumption(
            "2112316000", "E6E07422582221", group_by="month", order_by="period"
        )

        url = mock_session.get.call_args[0][0]
        assert "group_by=month" in url
        assert "order_by=period" in url

    @pytest.mark.asyncio
    async def test_no_extra_params_when_unset(
        self, mock_session, consumption_daily_response
    ):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_daily_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_consumption("1100009640372", "22L4344979")

        url = mock_session.get.call_args[0][0]
        assert "group_by" not in url
        assert "order_by" not in url
