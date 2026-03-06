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
def products_response() -> dict:
    """Return mock products API response."""
    return json.loads((FIXTURES / "products.json").read_text())
