"""Data models for the Octopus Energy API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class GridSupplyPoint:
    """A Grid Supply Point region."""

    group_id: str


@dataclass(frozen=True)
class Rate:
    """A unit rate for a tariff period."""

    value_exc_vat: float
    value_inc_vat: float
    valid_from: datetime
    valid_to: datetime | None = None


@dataclass(frozen=True)
class StandingCharge:
    """A standing charge for a tariff period."""

    value_exc_vat: float
    value_inc_vat: float
    valid_from: datetime
    valid_to: datetime | None = None


@dataclass(frozen=True)
class Consumption:
    """A single consumption reading."""

    consumption: float
    interval_start: datetime
    interval_end: datetime


@dataclass(frozen=True)
class Agreement:
    """A tariff agreement for a meter point."""

    tariff_code: str
    valid_from: datetime
    valid_to: datetime | None = None


@dataclass(frozen=True)
class Meter:
    """A meter (electricity or gas)."""

    serial_number: str


@dataclass(frozen=True)
class ElectricityMeterPoint:
    """An electricity meter point on an account."""

    mpan: str
    meters: list[Meter] = field(default_factory=list)
    agreements: list[Agreement] = field(default_factory=list)
    is_export: bool = False


@dataclass(frozen=True)
class GasMeterPoint:
    """A gas meter point on an account."""

    mprn: str
    meters: list[Meter] = field(default_factory=list)
    agreements: list[Agreement] = field(default_factory=list)


@dataclass(frozen=True)
class Property:
    """A property on an account."""

    id: int
    electricity_meter_points: list[ElectricityMeterPoint] = field(
        default_factory=list
    )
    gas_meter_points: list[GasMeterPoint] = field(default_factory=list)


@dataclass(frozen=True)
class Account:
    """An Octopus Energy account."""

    number: str
    properties: list[Property] = field(default_factory=list)
