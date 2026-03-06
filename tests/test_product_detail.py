"""Tests for ProductDetail, expanded Product model, and get_product_detail()."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from aiooctopusenergy import (
    DualRegisterTariff,
    OctopusEnergyClient,
    Product,
    ProductDetail,
    SingleRegisterTariff,
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


class TestProductDetailModel:
    def test_frozen(self):
        detail = ProductDetail(
            code="AGILE-24-10-01",
            full_name="Agile Octopus October 2024 v1",
            display_name="Agile Octopus",
            description="Test",
            is_variable=True,
            is_green=True,
            is_tracker=False,
            is_prepay=False,
            is_restricted=False,
            is_business=False,
            brand="OCTOPUS_ENERGY",
            term=12,
            available_from=None,
            available_to=None,
        )
        with pytest.raises(AttributeError):
            detail.code = "OTHER"

    def test_single_register_tariff_frozen(self):
        tariff = SingleRegisterTariff(
            code="E-1R-AGILE-24-10-01-A",
            standard_unit_rate_exc_vat=19.54,
            standard_unit_rate_inc_vat=20.517,
            standing_charge_exc_vat=37.6525,
            standing_charge_inc_vat=39.535125,
        )
        with pytest.raises(AttributeError):
            tariff.code = "OTHER"

    def test_dual_register_tariff_frozen(self):
        tariff = DualRegisterTariff(
            code="E-2R-AGILE-24-10-01-A",
            day_unit_rate_exc_vat=28.55,
            day_unit_rate_inc_vat=29.9775,
            night_unit_rate_exc_vat=7.5,
            night_unit_rate_inc_vat=7.875,
            standing_charge_exc_vat=37.6525,
            standing_charge_inc_vat=39.535125,
        )
        with pytest.raises(AttributeError):
            tariff.code = "OTHER"


class TestGetProductDetail:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, product_detail_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(product_detail_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_product_detail("AGILE-24-10-01")

        assert isinstance(result, ProductDetail)
        assert result.code == "AGILE-24-10-01"
        assert result.full_name == "Agile Octopus October 2024 v1"
        assert result.display_name == "Agile Octopus"
        assert result.is_variable is True
        assert result.is_green is True
        assert result.is_tracker is False
        assert result.is_prepay is False
        assert result.is_business is False
        assert result.brand == "OCTOPUS_ENERGY"
        assert result.term == 12
        assert result.available_from == datetime(2024, 9, 30, 23, 0, tzinfo=UTC)
        assert result.available_to is None

    @pytest.mark.asyncio
    async def test_single_register_electricity_regions(
        self, mock_session, product_detail_response
    ):
        mock_session.get = MagicMock(
            return_value=_mock_response(product_detail_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_product_detail("AGILE-24-10-01")

        assert set(result.single_register_electricity_tariffs.keys()) == {
            "_A",
            "_B",
            "_C",
        }
        tariff_a = result.single_register_electricity_tariffs["_A"]
        assert isinstance(tariff_a, SingleRegisterTariff)
        assert tariff_a.code == "E-1R-AGILE-24-10-01-A"
        assert tariff_a.standard_unit_rate_exc_vat == 19.54
        assert tariff_a.standard_unit_rate_inc_vat == 20.517
        assert tariff_a.standing_charge_exc_vat == 37.6525
        assert tariff_a.standing_charge_inc_vat == 39.535125

    @pytest.mark.asyncio
    async def test_dual_register_electricity_regions(
        self, mock_session, product_detail_response
    ):
        mock_session.get = MagicMock(
            return_value=_mock_response(product_detail_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_product_detail("AGILE-24-10-01")

        assert set(result.dual_register_electricity_tariffs.keys()) == {"_A", "_C"}
        tariff_a = result.dual_register_electricity_tariffs["_A"]
        assert isinstance(tariff_a, DualRegisterTariff)
        assert tariff_a.code == "E-2R-AGILE-24-10-01-A"
        assert tariff_a.day_unit_rate_exc_vat == 28.55
        assert tariff_a.night_unit_rate_exc_vat == 7.5

    @pytest.mark.asyncio
    async def test_single_register_gas_regions(
        self, mock_session, product_detail_response
    ):
        mock_session.get = MagicMock(
            return_value=_mock_response(product_detail_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_product_detail("AGILE-24-10-01")

        assert set(result.single_register_gas_tariffs.keys()) == {"_A", "_B"}
        tariff_a = result.single_register_gas_tariffs["_A"]
        assert tariff_a.code == "G-1R-AGILE-24-10-01-A"
        assert tariff_a.standard_unit_rate_exc_vat == 6.76

    @pytest.mark.asyncio
    async def test_no_auth_used(self, mock_session, product_detail_response):
        mock_session.get = MagicMock(
            return_value=_mock_response(product_detail_response)
        )
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_product_detail("AGILE-24-10-01")

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_payment_method_iteration(self, mock_session):
        """Parser takes the first payment method value regardless of key name."""
        data = {
            "code": "PREPAY-VAR-22-11-01",
            "full_name": "Prepay Variable",
            "display_name": "Prepay Variable",
            "description": "",
            "is_variable": True,
            "is_green": False,
            "is_tracker": False,
            "is_prepay": True,
            "is_business": False,
            "is_restricted": False,
            "brand": "OCTOPUS_ENERGY",
            "term": None,
            "available_from": None,
            "available_to": None,
            "single_register_electricity_tariffs": {
                "_A": {
                    "varying": {
                        "code": "E-1R-PREPAY-VAR-22-11-01-A",
                        "standard_unit_rate_exc_vat": 25.0,
                        "standard_unit_rate_inc_vat": 26.25,
                        "standing_charge_exc_vat": 40.0,
                        "standing_charge_inc_vat": 42.0,
                    }
                }
            },
            "dual_register_electricity_tariffs": {},
            "single_register_gas_tariffs": {},
        }
        mock_session.get = MagicMock(return_value=_mock_response(data))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_product_detail("PREPAY-VAR-22-11-01")

        tariff = result.single_register_electricity_tariffs["_A"]
        assert tariff.code == "E-1R-PREPAY-VAR-22-11-01-A"
        assert tariff.standard_unit_rate_exc_vat == 25.0

    @pytest.mark.asyncio
    async def test_empty_tariff_sections(self, mock_session):
        """Product with no tariff data returns empty dicts."""
        data = {
            "code": "TEST-01",
            "full_name": "Test Product",
            "display_name": "Test",
            "description": "",
            "is_variable": False,
            "is_green": False,
            "is_tracker": False,
            "is_prepay": False,
            "is_business": False,
            "is_restricted": False,
            "brand": "OCTOPUS_ENERGY",
            "term": None,
            "available_from": None,
            "available_to": None,
            "single_register_electricity_tariffs": {},
            "dual_register_electricity_tariffs": {},
            "single_register_gas_tariffs": {},
        }
        mock_session.get = MagicMock(return_value=_mock_response(data))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_product_detail("TEST-01")

        assert result.single_register_electricity_tariffs == {}
        assert result.dual_register_electricity_tariffs == {}
        assert result.single_register_gas_tariffs == {}


class TestExpandedProductFields:
    @pytest.mark.asyncio
    async def test_new_fields_populated(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_products()

        agile = result[0]
        assert agile.is_green is True
        assert agile.is_tracker is False
        assert agile.is_prepay is False
        assert agile.is_restricted is False
        assert agile.term == 12
        assert agile.available_from == datetime(2024, 9, 30, 23, 0, tzinfo=UTC)
        assert agile.available_to is None

    @pytest.mark.asyncio
    async def test_null_term(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_products()

        flexible = result[1]
        assert flexible.term is None

    def test_backward_compatible_defaults(self):
        """Product can still be created with original fields only."""
        product = Product(
            code="TEST",
            full_name="Test",
            display_name="Test",
            description="",
            is_variable=True,
            brand="OCTOPUS_ENERGY",
        )
        assert product.is_green is False
        assert product.term is None
        assert product.available_from is None


class TestGetProductsFilters:
    @pytest.mark.asyncio
    async def test_is_green_filter(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products(is_green=True)

        url = mock_session.get.call_args[0][0]
        assert "is_green=true" in url

    @pytest.mark.asyncio
    async def test_is_prepay_filter(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products(is_prepay=False)

        url = mock_session.get.call_args[0][0]
        assert "is_prepay=false" in url

    @pytest.mark.asyncio
    async def test_is_tracker_filter(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products(is_tracker=True)

        url = mock_session.get.call_args[0][0]
        assert "is_tracker=true" in url

    @pytest.mark.asyncio
    async def test_brand_filter(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products(brand="OCTOPUS_ENERGY")

        url = mock_session.get.call_args[0][0]
        assert "brand=OCTOPUS_ENERGY" in url

    @pytest.mark.asyncio
    async def test_available_at_filter(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        dt = datetime(2026, 3, 6, tzinfo=UTC)
        await client.get_products(available_at=dt)

        url = mock_session.get.call_args[0][0]
        assert "available_at=" in url
