"""Tests for data models."""

from __future__ import annotations

from datetime import UTC, datetime

from aiooctopusenergy import (
    Account,
    Agreement,
    Consumption,
    ElectricityMeterPoint,
    GasMeterPoint,
    GridSupplyPoint,
    Meter,
    Property,
    Rate,
    StandingCharge,
)


class TestModelsImmutable:
    def test_rate_frozen(self):
        rate = Rate(
            value_exc_vat=19.54,
            value_inc_vat=20.517,
            valid_from=datetime(2026, 3, 6, 22, 30, tzinfo=UTC),
            valid_to=datetime(2026, 3, 6, 23, 0, tzinfo=UTC),
        )
        assert rate.value_inc_vat == 20.517
        with __import__("pytest").raises(AttributeError):
            rate.value_inc_vat = 0  # type: ignore[misc]

    def test_consumption_frozen(self):
        reading = Consumption(
            consumption=0.234,
            interval_start=datetime(2026, 3, 5, 23, 30, tzinfo=UTC),
            interval_end=datetime(2026, 3, 6, 0, 0, tzinfo=UTC),
        )
        assert reading.consumption == 0.234

    def test_grid_supply_point(self):
        gsp = GridSupplyPoint(group_id="_B")
        assert gsp.group_id == "_B"

    def test_standing_charge_optional_valid_to(self):
        charge = StandingCharge(
            value_exc_vat=37.65,
            value_inc_vat=39.53,
            valid_from=datetime(2024, 10, 1, tzinfo=UTC),
        )
        assert charge.valid_to is None


class TestAccountStructure:
    def test_nested_structure(self):
        account = Account(
            number="A-AAAA1111",
            properties=[
                Property(
                    id=1,
                    electricity_meter_points=[
                        ElectricityMeterPoint(
                            mpan="1234567890",
                            meters=[Meter(serial_number="ABC123")],
                            agreements=[
                                Agreement(
                                    tariff_code="E-1R-AGILE-24-10-01-C",
                                    valid_from=datetime(2024, 10, 1, tzinfo=UTC),
                                )
                            ],
                        )
                    ],
                    gas_meter_points=[
                        GasMeterPoint(
                            mprn="9876543210",
                            meters=[Meter(serial_number="GAS456")],
                        )
                    ],
                )
            ],
        )
        assert account.number == "A-AAAA1111"
        assert account.properties[0].electricity_meter_points[0].mpan == "1234567890"
        assert account.properties[0].gas_meter_points[0].mprn == "9876543210"

    def test_default_empty_lists(self):
        account = Account(number="A-AAAA1111")
        assert account.properties == []

        prop = Property(id=1)
        assert prop.electricity_meter_points == []
        assert prop.gas_meter_points == []
