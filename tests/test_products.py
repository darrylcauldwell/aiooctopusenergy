"""Tests for Product model and get_products()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from aiooctopusenergy import OctopusEnergyClient, Product


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


class TestProductModel:
    def test_frozen(self):
        product = Product(
            code="AGILE-24-10-01",
            full_name="Agile Octopus October 2024 v1",
            display_name="Agile Octopus",
            description="Half-hourly energy prices.",
            is_variable=True,
            brand="OCTOPUS_ENERGY",
        )
        with pytest.raises(AttributeError):
            product.code = "OTHER"

    def test_fields(self):
        product = Product(
            code="VAR-22-11-01",
            full_name="Flexible Octopus November 2022 v1",
            display_name="Flexible Octopus",
            description="Standard variable tariff.",
            is_variable=True,
            brand="OCTOPUS_ENERGY",
        )
        assert product.code == "VAR-22-11-01"
        assert product.display_name == "Flexible Octopus"
        assert product.is_variable is True


class TestGetProducts:
    @pytest.mark.asyncio
    async def test_success(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_products()

        assert len(result) == 3
        assert all(isinstance(p, Product) for p in result)

        agile = result[0]
        assert agile.code == "AGILE-24-10-01"
        assert agile.full_name == "Agile Octopus October 2024 v1"
        assert agile.display_name == "Agile Octopus"
        assert agile.is_variable is True
        assert agile.brand == "OCTOPUS_ENERGY"

        go = result[2]
        assert go.code == "GO-VAR-22-10-14"
        assert go.display_name == "Octopus Go"

    @pytest.mark.asyncio
    async def test_no_auth_used(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products()

        call_kwargs = mock_session.get.call_args
        assert "auth" not in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_filter_variable(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products(is_variable=True)

        call_args = mock_session.get.call_args
        url = call_args[0][0]
        assert "is_variable=true" in url

    @pytest.mark.asyncio
    async def test_filter_fixed(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products(is_variable=False)

        call_args = mock_session.get.call_args
        url = call_args[0][0]
        assert "is_variable=false" in url

    @pytest.mark.asyncio
    async def test_business_filter_default(self, mock_session, products_response):
        mock_session.get = MagicMock(return_value=_mock_response(products_response))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        await client.get_products()

        call_args = mock_session.get.call_args
        url = call_args[0][0]
        assert "is_business=false" in url

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_session):
        empty = {"count": 0, "next": None, "previous": None, "results": []}
        mock_session.get = MagicMock(return_value=_mock_response(empty))
        client = OctopusEnergyClient(api_key="sk_live_test", session=mock_session)

        result = await client.get_products()

        assert result == []
