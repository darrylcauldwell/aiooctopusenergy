"""Async client for the Octopus Energy REST API."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Self

import aiohttp

from .const import BASE_URL, DEFAULT_PAGE_SIZE
from .exceptions import (
    OctopusEnergyAuthenticationError,
    OctopusEnergyConnectionError,
    OctopusEnergyError,
    OctopusEnergyNotFoundError,
    OctopusEnergyRateLimitError,
    OctopusEnergyTimeoutError,
)
from .models import (
    Account,
    Agreement,
    Consumption,
    DualRegisterTariff,
    ElectricityMeterPoint,
    GasMeterPoint,
    GridSupplyPoint,
    Meter,
    Product,
    ProductDetail,
    Property,
    Rate,
    SingleRegisterTariff,
    StandingCharge,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


def _format_datetime(dt: datetime) -> str:
    """Format a datetime for use in API URL parameters.

    The Octopus Energy API rejects '+00:00' in URL query params because
    the '+' is interpreted as a space. Use 'Z' suffix for UTC instead.
    """
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    return iso


class OctopusEnergyClient:
    """Async client for the Octopus Energy REST API.

    Can be used as a context manager or standalone. When used standalone,
    pass an existing aiohttp.ClientSession to avoid creating a new one.
    """

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the client."""
        self._api_key = api_key
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        if self._owns_session:
            self._session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def _get(self, path: str, *, auth: bool = True) -> dict:
        """Make a GET request to the API."""
        if self._session is None:
            msg = "Session not initialized. Use as context manager or pass a session."
            raise OctopusEnergyError(msg)

        url = f"{BASE_URL}{path}"
        kwargs: dict = {"timeout": REQUEST_TIMEOUT}
        if auth:
            kwargs["auth"] = aiohttp.BasicAuth(self._api_key, "")

        try:
            async with self._session.get(url, **kwargs) as resp:
                if resp.status == 401:
                    msg = "Invalid API key"
                    raise OctopusEnergyAuthenticationError(msg)
                if resp.status == 404:
                    msg = f"Resource not found: {path}"
                    raise OctopusEnergyNotFoundError(msg)
                if resp.status == 429:
                    msg = f"Rate limited: {path}"
                    raise OctopusEnergyRateLimitError(msg)
                if resp.status != 200:
                    msg = f"API returned status {resp.status}"
                    raise OctopusEnergyError(msg)
                return await resp.json()
        except (
            OctopusEnergyAuthenticationError,
            OctopusEnergyNotFoundError,
            OctopusEnergyRateLimitError,
        ):
            raise
        except TimeoutError as err:
            msg = f"Timeout connecting to {url}"
            raise OctopusEnergyTimeoutError(msg) from err
        except aiohttp.ClientError as err:
            msg = f"Error connecting to {url}"
            raise OctopusEnergyConnectionError(msg) from err

    async def _get_paginated(
        self,
        path: str,
        *,
        auth: bool = True,
        page_size: int = DEFAULT_PAGE_SIZE,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        extra_params: dict[str, str] | None = None,
        page_delay: float = 0.0,
    ) -> list[dict]:
        """Fetch all pages from a paginated endpoint.

        Args:
            page_delay: Seconds to wait between consecutive page fetches.
                        Useful for avoiding per-endpoint rate limits on
                        large historical queries.
        """
        params: list[str] = [f"page_size={page_size}"]
        if period_from:
            params.append(f"period_from={_format_datetime(period_from)}")
        if period_to:
            params.append(f"period_to={_format_datetime(period_to)}")
        if extra_params:
            for key, value in extra_params.items():
                params.append(f"{key}={value}")

        separator = "&" if "?" in path else "?"
        url = f"{path}{separator}{'&'.join(params)}"

        all_results: list[dict] = []
        page_count = 0
        while url:
            if page_count > 0 and page_delay > 0:
                await asyncio.sleep(page_delay)
            data = await self._get(url, auth=auth)
            all_results.extend(data.get("results", []))
            next_url = data.get("next")
            if next_url and next_url.startswith(BASE_URL):
                url = next_url[len(BASE_URL) :]
            else:
                url = ""
            page_count += 1

        return all_results

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parse an ISO datetime string from the API."""
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _require_datetime(value: str) -> datetime:
        """Parse a required ISO datetime string."""
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _parse_account(self, data: dict) -> Account:
        """Parse account data from the API response."""
        properties = []
        for prop in data.get("properties", []):
            elec_points = []
            for ep in prop.get("electricity_meter_points", []):
                meters = [
                    Meter(serial_number=m["serial_number"])
                    for m in ep.get("meters", [])
                ]
                agreements = [
                    Agreement(
                        tariff_code=a["tariff_code"],
                        valid_from=self._require_datetime(a["valid_from"]),
                        valid_to=self._parse_datetime(a.get("valid_to")),
                    )
                    for a in ep.get("agreements", [])
                ]
                elec_points.append(
                    ElectricityMeterPoint(
                        mpan=ep["mpan"],
                        meters=meters,
                        agreements=agreements,
                        is_export=ep.get("is_export", False),
                    )
                )

            gas_points = []
            for gp in prop.get("gas_meter_points", []):
                meters = [
                    Meter(serial_number=m["serial_number"])
                    for m in gp.get("meters", [])
                ]
                agreements = [
                    Agreement(
                        tariff_code=a["tariff_code"],
                        valid_from=self._require_datetime(a["valid_from"]),
                        valid_to=self._parse_datetime(a.get("valid_to")),
                    )
                    for a in gp.get("agreements", [])
                ]
                gas_points.append(
                    GasMeterPoint(
                        mprn=gp["mprn"],
                        meters=meters,
                        agreements=agreements,
                    )
                )

            properties.append(
                Property(
                    id=prop["id"],
                    electricity_meter_points=elec_points,
                    gas_meter_points=gas_points,
                )
            )

        return Account(number=data["number"], properties=properties)

    async def get_account(self, account_number: str) -> Account:
        """Get account details including meters and tariff history.

        Args:
            account_number: Octopus Energy account number (e.g. "A-AAAA1111").

        Returns:
            Account with properties, meter points, and agreements.
        """
        data = await self._get(f"/v1/accounts/{account_number}/")
        return self._parse_account(data)

    async def get_electricity_consumption(
        self,
        mpan: str,
        serial_number: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        group_by: str | None = None,
        order_by: str | None = None,
        page_delay: float = 0.0,
    ) -> list[Consumption]:
        """Get electricity consumption readings.

        Args:
            mpan: Meter Point Administration Number.
            serial_number: Meter serial number.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.
            group_by: Aggregate by period: "day", "week", "month", "quarter".
            order_by: Sort order: "period" for ascending.
            page_delay: Seconds to wait between pagination requests.

        Returns:
            List of consumption readings.
        """
        path = (
            f"/v1/electricity-meter-points/{mpan}"
            f"/meters/{serial_number}/consumption/"
        )
        extra: dict[str, str] = {}
        if group_by:
            extra["group_by"] = group_by
        if order_by:
            extra["order_by"] = order_by
        results = await self._get_paginated(
            path,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
            extra_params=extra if extra else None,
            page_delay=page_delay,
        )
        return [
            Consumption(
                consumption=r["consumption"],
                interval_start=self._require_datetime(r["interval_start"]),
                interval_end=self._require_datetime(r["interval_end"]),
            )
            for r in results
            if r.get("interval_start") is not None
        ]

    async def get_gas_consumption(
        self,
        mprn: str,
        serial_number: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        group_by: str | None = None,
        order_by: str | None = None,
    ) -> list[Consumption]:
        """Get gas consumption readings.

        Args:
            mprn: Meter Point Reference Number.
            serial_number: Meter serial number.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.
            group_by: Aggregate by period: "day", "week", "month", "quarter".
            order_by: Sort order: "period" for ascending.

        Returns:
            List of consumption readings.
        """
        path = (
            f"/v1/gas-meter-points/{mprn}"
            f"/meters/{serial_number}/consumption/"
        )
        extra: dict[str, str] = {}
        if group_by:
            extra["group_by"] = group_by
        if order_by:
            extra["order_by"] = order_by
        results = await self._get_paginated(
            path,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
            extra_params=extra if extra else None,
        )
        return [
            Consumption(
                consumption=r["consumption"],
                interval_start=self._require_datetime(r["interval_start"]),
                interval_end=self._require_datetime(r["interval_end"]),
            )
            for r in results
            if r.get("interval_start") is not None
        ]

    async def get_electricity_rates(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Rate]:
        """Get electricity unit rates for a tariff.

        Args:
            product_code: Product code (e.g. "AGILE-24-10-01").
            tariff_code: Tariff code (e.g. "E-1R-AGILE-24-10-01-C").
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of rates ordered by valid_from descending.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/electricity-tariffs/{tariff_code}/standard-unit-rates/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Rate(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_electricity_standing_charges(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[StandingCharge]:
        """Get electricity standing charges for a tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of standing charges.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/electricity-tariffs/{tariff_code}/standing-charges/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            StandingCharge(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_gas_rates(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Rate]:
        """Get gas unit rates for a tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of rates.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/gas-tariffs/{tariff_code}/standard-unit-rates/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Rate(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_gas_standing_charges(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[StandingCharge]:
        """Get gas standing charges for a tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of standing charges.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/gas-tariffs/{tariff_code}/standing-charges/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            StandingCharge(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_electricity_day_rates(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Rate]:
        """Get electricity day unit rates for a dual-register tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code (E-2R prefix).
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of day rates.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/electricity-tariffs/{tariff_code}/day-unit-rates/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Rate(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_electricity_night_rates(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Rate]:
        """Get electricity night unit rates for a dual-register tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code (E-2R prefix).
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of night rates.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/electricity-tariffs/{tariff_code}/night-unit-rates/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Rate(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_gas_day_rates(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Rate]:
        """Get gas day unit rates for a dual-register tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of day rates.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/gas-tariffs/{tariff_code}/day-unit-rates/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Rate(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_gas_night_rates(
        self,
        product_code: str,
        tariff_code: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Rate]:
        """Get gas night unit rates for a dual-register tariff.

        Args:
            product_code: Product code.
            tariff_code: Tariff code.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of night rates.
        """
        path = (
            f"/v1/products/{product_code}"
            f"/gas-tariffs/{tariff_code}/night-unit-rates/"
        )
        results = await self._get_paginated(
            path,
            auth=False,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Rate(
                value_exc_vat=r["value_exc_vat"],
                value_inc_vat=r["value_inc_vat"],
                valid_from=self._require_datetime(r["valid_from"]),
                valid_to=self._parse_datetime(r.get("valid_to")),
            )
            for r in results
            if r.get("valid_from") is not None
        ]

    async def get_products(
        self,
        *,
        is_variable: bool | None = None,
        is_business: bool = False,
        is_green: bool | None = None,
        is_prepay: bool | None = None,
        is_tracker: bool | None = None,
        brand: str | None = None,
        available_at: datetime | None = None,
    ) -> list[Product]:
        """Get available energy products.

        Args:
            is_variable: Filter by variable/fixed. None returns all.
            is_business: Include business products. Defaults to False.
            is_green: Filter by green tariffs. None returns all.
            is_prepay: Filter by prepay tariffs. None returns all.
            is_tracker: Filter by tracker tariffs. None returns all.
            brand: Filter by brand name.
            available_at: Filter products available at this datetime.

        Returns:
            List of available products.
        """
        params: list[str] = []
        if is_variable is not None:
            params.append(f"is_variable={'true' if is_variable else 'false'}")
        if not is_business:
            params.append("is_business=false")
        if is_green is not None:
            params.append(f"is_green={'true' if is_green else 'false'}")
        if is_prepay is not None:
            params.append(f"is_prepay={'true' if is_prepay else 'false'}")
        if is_tracker is not None:
            params.append(f"is_tracker={'true' if is_tracker else 'false'}")
        if brand is not None:
            params.append(f"brand={brand}")
        if available_at is not None:
            params.append(f"available_at={_format_datetime(available_at)}")

        query = f"?{'&'.join(params)}" if params else ""
        data = await self._get(f"/v1/products/{query}", auth=False)
        return [
            Product(
                code=r["code"],
                full_name=r["full_name"],
                display_name=r["display_name"],
                description=r.get("description", ""),
                is_variable=r["is_variable"],
                brand=r["brand"],
                is_green=r.get("is_green", False),
                is_tracker=r.get("is_tracker", False),
                is_prepay=r.get("is_prepay", False),
                is_restricted=r.get("is_restricted", False),
                term=r.get("term"),
                available_from=self._parse_datetime(r.get("available_from")),
                available_to=self._parse_datetime(r.get("available_to")),
            )
            for r in data.get("results", [])
        ]

    @staticmethod
    def _parse_single_register_tariff(
        region_data: dict,
    ) -> SingleRegisterTariff | None:
        """Parse a single-register tariff from a region's payment method data."""
        for tariff_data in region_data.values():
            return SingleRegisterTariff(
                code=tariff_data["code"],
                standard_unit_rate_exc_vat=tariff_data["standard_unit_rate_exc_vat"],
                standard_unit_rate_inc_vat=tariff_data["standard_unit_rate_inc_vat"],
                standing_charge_exc_vat=tariff_data["standing_charge_exc_vat"],
                standing_charge_inc_vat=tariff_data["standing_charge_inc_vat"],
            )
        return None

    @staticmethod
    def _parse_dual_register_tariff(
        region_data: dict,
    ) -> DualRegisterTariff | None:
        """Parse a dual-register tariff from a region's payment method data."""
        for tariff_data in region_data.values():
            return DualRegisterTariff(
                code=tariff_data["code"],
                day_unit_rate_exc_vat=tariff_data["day_unit_rate_exc_vat"],
                day_unit_rate_inc_vat=tariff_data["day_unit_rate_inc_vat"],
                night_unit_rate_exc_vat=tariff_data["night_unit_rate_exc_vat"],
                night_unit_rate_inc_vat=tariff_data["night_unit_rate_inc_vat"],
                standing_charge_exc_vat=tariff_data["standing_charge_exc_vat"],
                standing_charge_inc_vat=tariff_data["standing_charge_inc_vat"],
            )
        return None

    async def get_product_detail(self, product_code: str) -> ProductDetail:
        """Get detailed product info including regional tariffs.

        Args:
            product_code: Product code (e.g. "AGILE-24-10-01").

        Returns:
            ProductDetail with regional tariff information.
        """
        data = await self._get(f"/v1/products/{product_code}/", auth=False)

        single_elec: dict[str, SingleRegisterTariff] = {}
        for region, region_data in data.get(
            "single_register_electricity_tariffs", {}
        ).items():
            tariff = self._parse_single_register_tariff(region_data)
            if tariff:
                single_elec[region] = tariff

        dual_elec: dict[str, DualRegisterTariff] = {}
        for region, region_data in data.get(
            "dual_register_electricity_tariffs", {}
        ).items():
            tariff = self._parse_dual_register_tariff(region_data)
            if tariff:
                dual_elec[region] = tariff

        single_gas: dict[str, SingleRegisterTariff] = {}
        for region, region_data in data.get(
            "single_register_gas_tariffs", {}
        ).items():
            tariff = self._parse_single_register_tariff(region_data)
            if tariff:
                single_gas[region] = tariff

        return ProductDetail(
            code=data["code"],
            full_name=data["full_name"],
            display_name=data["display_name"],
            description=data.get("description", ""),
            is_variable=data["is_variable"],
            is_green=data.get("is_green", False),
            is_tracker=data.get("is_tracker", False),
            is_prepay=data.get("is_prepay", False),
            is_restricted=data.get("is_restricted", False),
            is_business=data.get("is_business", False),
            brand=data.get("brand", ""),
            term=data.get("term"),
            available_from=self._parse_datetime(data.get("available_from")),
            available_to=self._parse_datetime(data.get("available_to")),
            single_register_electricity_tariffs=single_elec,
            dual_register_electricity_tariffs=dual_elec,
            single_register_gas_tariffs=single_gas,
        )

    async def get_grid_supply_points(
        self, postcode: str
    ) -> list[GridSupplyPoint]:
        """Look up Grid Supply Point regions by postcode.

        Args:
            postcode: UK postcode (full or outward part).

        Returns:
            List of Grid Supply Point regions.
        """
        data = await self._get(
            f"/v1/industry/grid-supply-points/?postcode={postcode}",
            auth=False,
        )
        return [
            GridSupplyPoint(group_id=r["group_id"])
            for r in data.get("results", [])
        ]
