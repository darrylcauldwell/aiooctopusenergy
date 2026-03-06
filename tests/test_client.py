"""Tests for OctopusEnergyClient."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from aiooctopusenergy import (
    OctopusEnergyAuthenticationError,
    OctopusEnergyClient,
    OctopusEnergyConnectionError,
    OctopusEnergyError,
    OctopusEnergyNotFoundError,
    OctopusEnergyTimeoutError,
)


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


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, account_response):
        mock_session.get = MagicMock(return_value=_mock_response(account_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_account("A-AAAA1111")

        assert result.number == "A-AAAA1111"
        assert len(result.properties) == 1

        prop = result.properties[0]
        assert prop.id == 12345
        assert len(prop.electricity_meter_points) == 2
        assert len(prop.gas_meter_points) == 1

        import_meter = prop.electricity_meter_points[0]
        assert import_meter.mpan == "1100009640372"
        assert import_meter.is_export is False
        assert len(import_meter.meters) == 1
        assert import_meter.meters[0].serial_number == "22L4344979"
        assert len(import_meter.agreements) == 2
        assert import_meter.agreements[0].tariff_code == "E-1R-AGILE-24-10-01-C"
        assert import_meter.agreements[0].valid_to is None

        export_meter = prop.electricity_meter_points[1]
        assert export_meter.mpan == "1170001806920"
        assert export_meter.is_export is True

        gas = prop.gas_meter_points[0]
        assert gas.mprn == "2112316000"
        assert gas.meters[0].serial_number == "E6E07422582221"

    @pytest.mark.asyncio
    async def test_uses_auth(self, mock_session, account_response):
        mock_session.get = MagicMock(return_value=_mock_response(account_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_account("A-AAAA1111")

        call_kwargs = mock_session.get.call_args
        assert "auth" in call_kwargs.kwargs


class TestGetElectricityConsumption:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, consumption_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_consumption(
            "1100009640372", "22L4344979"
        )

        assert len(result) == 4
        assert result[0].consumption == 0.234
        assert result[0].interval_start == datetime(
            2026, 3, 5, 23, 30, tzinfo=UTC
        )
        assert result[3].consumption == 0.123

    @pytest.mark.asyncio
    async def test_with_period_filter(self, mock_session, consumption_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        period_from = datetime(2026, 3, 5, tzinfo=UTC)
        period_to = datetime(2026, 3, 6, tzinfo=UTC)
        await client.get_electricity_consumption(
            "1100009640372",
            "22L4344979",
            period_from=period_from,
            period_to=period_to,
        )

        url = mock_session.get.call_args[0][0]
        assert "period_from=" in url
        assert "period_to=" in url

    @pytest.mark.asyncio
    async def test_pagination(
        self, mock_session, consumption_page1_response, consumption_page2_response
    ):
        mock_session.get = MagicMock(
            side_effect=[
                _mock_response(consumption_page1_response),
                _mock_response(consumption_page2_response),
            ]
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_consumption(
            "1100009640372", "22L4344979", page_size=2
        )

        assert len(result) == 4
        assert result[0].consumption == 0.234
        assert result[3].consumption == 0.123
        assert mock_session.get.call_count == 2


class TestGetGasConsumption:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, consumption_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(consumption_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_gas_consumption("2112316000", "E6E07422582221")

        assert len(result) == 4
        assert result[0].consumption == 0.234


class TestGetElectricityRates:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, rates_response):
        mock_session.get = MagicMock(return_value=_mock_response(rates_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_rates(
            "AGILE-24-10-01", "E-1R-AGILE-24-10-01-C"
        )

        assert len(result) == 3
        assert result[0].value_exc_vat == 19.54
        assert result[0].value_inc_vat == 20.517
        assert result[0].valid_from == datetime(2026, 3, 6, 22, 30, tzinfo=UTC)
        assert result[0].valid_to == datetime(2026, 3, 6, 23, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_no_auth(self, mock_session, rates_response):
        mock_session.get = MagicMock(return_value=_mock_response(rates_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_electricity_rates(
            "AGILE-24-10-01", "E-1R-AGILE-24-10-01-C"
        )

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs


class TestGetStandingCharges:
    @pytest.mark.asyncio
    async def test_electricity(self, mock_session, standing_charges_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(standing_charges_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_electricity_standing_charges(
            "AGILE-24-10-01", "E-1R-AGILE-24-10-01-C"
        )

        assert len(result) == 1
        assert result[0].value_exc_vat == 37.6525
        assert result[0].value_inc_vat == 39.535125
        assert result[0].valid_to is None

    @pytest.mark.asyncio
    async def test_gas(self, mock_session, standing_charges_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(standing_charges_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_gas_standing_charges(
            "VAR-22-11-01", "G-1R-VAR-22-11-01-C"
        )

        assert len(result) == 1
        assert result[0].value_exc_vat == 37.6525


class TestGetGasRates:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, rates_response):
        mock_session.get = MagicMock(return_value=_mock_response(rates_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_gas_rates(
            "VAR-22-11-01", "G-1R-VAR-22-11-01-C"
        )

        assert len(result) == 3
        assert result[0].value_exc_vat == 19.54


class TestGetGridSupplyPoints:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, grid_supply_points_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(grid_supply_points_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_grid_supply_points("DE45")

        assert len(result) == 1
        assert result[0].group_id == "_B"

    @pytest.mark.asyncio
    async def test_no_auth(self, mock_session, grid_supply_points_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(grid_supply_points_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_grid_supply_points("DE45")

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_authentication_error(self, mock_session):
        mock_session.get = MagicMock(return_value=_mock_response({}, status=401))
        client = OctopusEnergyClient(api_key="bad_key", session=mock_session)

        with pytest.raises(OctopusEnergyAuthenticationError):
            await client.get_account("A-AAAA1111")

    @pytest.mark.asyncio
    async def test_not_found_error(self, mock_session):
        mock_session.get = MagicMock(return_value=_mock_response({}, status=404))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        with pytest.raises(OctopusEnergyNotFoundError):
            await client.get_account("A-XXXX0000")

    @pytest.mark.asyncio
    async def test_server_error(self, mock_session):
        mock_session.get = MagicMock(return_value=_mock_response({}, status=500))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        with pytest.raises(OctopusEnergyError, match="status 500"):
            await client.get_account("A-AAAA1111")

    @pytest.mark.asyncio
    async def test_timeout_error(self, mock_session):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=TimeoutError)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=ctx)
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        with pytest.raises(OctopusEnergyTimeoutError):
            await client.get_account("A-AAAA1111")

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_session):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientConnectionError("Connection refused")
        )
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=ctx)
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        with pytest.raises(OctopusEnergyConnectionError):
            await client.get_account("A-AAAA1111")

    @pytest.mark.asyncio
    async def test_no_session_error(self):
        client = OctopusEnergyClient(api_key="sk_live_test")

        with pytest.raises(OctopusEnergyError, match="Session not initialized"):
            await client.get_account("A-AAAA1111")


class TestContextManager:
    @pytest.mark.asyncio
    async def test_creates_and_closes_session(self):
        async with OctopusEnergyClient(api_key="sk_live_test") as client:
            assert client._session is not None
        assert client._session is None

    @pytest.mark.asyncio
    async def test_external_session_not_closed(self, mock_session):
        mock_session.close = AsyncMock()
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.close()
        mock_session.close.assert_not_called()
