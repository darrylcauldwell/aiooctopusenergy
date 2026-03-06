"""Test fixtures for aiooctopusenergy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def account_response() -> dict:
    """Return mock account API response."""
    return json.loads((FIXTURES / "account.json").read_text())


@pytest.fixture
def consumption_response() -> dict:
    """Return mock consumption API response."""
    return json.loads((FIXTURES / "consumption.json").read_text())


@pytest.fixture
def consumption_page1_response() -> dict:
    """Return mock first page of paginated consumption."""
    return json.loads((FIXTURES / "consumption_paginated_page1.json").read_text())


@pytest.fixture
def consumption_page2_response() -> dict:
    """Return mock second page of paginated consumption."""
    return json.loads((FIXTURES / "consumption_paginated_page2.json").read_text())


@pytest.fixture
def rates_response() -> dict:
    """Return mock rates API response."""
    return json.loads((FIXTURES / "rates.json").read_text())


@pytest.fixture
def standing_charges_response() -> dict:
    """Return mock standing charges API response."""
    return json.loads((FIXTURES / "standing_charges.json").read_text())


@pytest.fixture
def grid_supply_points_response() -> dict:
    """Return mock GSP API response."""
    return json.loads((FIXTURES / "grid_supply_points.json").read_text())


@pytest.fixture
def day_rates_response() -> dict:
    """Return mock day rates API response."""
    return json.loads((FIXTURES / "day_rates.json").read_text())


@pytest.fixture
def night_rates_response() -> dict:
    """Return mock night rates API response."""
    return json.loads((FIXTURES / "night_rates.json").read_text())


@pytest.fixture
def consumption_daily_response() -> dict:
    """Return mock daily consumption API response."""
    return json.loads((FIXTURES / "consumption_daily.json").read_text())


@pytest.fixture
def products_response() -> dict:
    """Return mock products API response."""
    return json.loads((FIXTURES / "products.json").read_text())


@pytest.fixture
def product_detail_response() -> dict:
    """Return mock product detail API response."""
    return json.loads((FIXTURES / "product_detail.json").read_text())


@pytest.fixture
def applicable_rates_graphql_response() -> dict:
    """Return mock GraphQL applicable rates response."""
    return json.loads((FIXTURES / "applicable_rates_graphql.json").read_text())


@pytest.fixture
def applicable_rates_paginated_response() -> dict:
    """Return mock GraphQL applicable rates page 1."""
    return json.loads((FIXTURES / "applicable_rates_paginated.json").read_text())


@pytest.fixture
def applicable_rates_page2_response() -> dict:
    """Return mock GraphQL applicable rates page 2."""
    return json.loads((FIXTURES / "applicable_rates_page2.json").read_text())


@pytest.fixture
def solar_estimate_graphql_response() -> dict:
    """Return mock GraphQL solar estimate response."""
    return json.loads((FIXTURES / "solar_estimate_graphql.json").read_text())


@pytest.fixture
def tariff_comparison_graphql_response() -> dict:
    """Return mock GraphQL tariff comparison response."""
    return json.loads((FIXTURES / "tariff_comparison_graphql.json").read_text())
