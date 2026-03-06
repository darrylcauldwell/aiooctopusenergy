"""Async client for the Octopus Energy REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Self

import aiohttp

from .const import BASE_URL, DEFAULT_PAGE_SIZE
from .exceptions import (
    OctopusEnergyAuthenticationError,
    OctopusEnergyConnectionError,
    OctopusEnergyError,
    OctopusEnergyNotFoundError,
    OctopusEnergyTimeoutError,
)
from .models import (
    Account,
    Agreement,
    Consumption,
    ElectricityMeterPoint,
    GasMeterPoint,
    GridSupplyPoint,
    Meter,
    Product,
    Property,
    Rate,
    StandingCharge,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


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
                if resp.status != 200:
                    msg = f"API returned status {resp.status}"
                    raise OctopusEnergyError(msg)
                return await resp.json()
        except (OctopusEnergyAuthenticationError, OctopusEnergyNotFoundError):
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
    ) -> list[dict]:
        """Fetch all pages from a paginated endpoint."""
        params: list[str] = [f"page_size={page_size}"]
        if period_from:
            params.append(f"period_from={period_from.isoformat()}")
        if period_to:
            params.append(f"period_to={period_to.isoformat()}")

        separator = "&" if "?" in path else "?"
        url = f"{path}{separator}{'&'.join(params)}"

        all_results: list[dict] = []
        while url:
            data = await self._get(url, auth=auth)
            all_results.extend(data.get("results", []))
            next_url = data.get("next")
            if next_url and next_url.startswith(BASE_URL):
                url = next_url[len(BASE_URL) :]
            else:
                url = ""

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
    ) -> list[Consumption]:
        """Get half-hourly electricity consumption readings.

        Args:
            mpan: Meter Point Administration Number.
            serial_number: Meter serial number.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of consumption readings ordered by interval_start descending.
        """
        path = (
            f"/v1/electricity-meter-points/{mpan}"
            f"/meters/{serial_number}/consumption/"
        )
        results = await self._get_paginated(
            path,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Consumption(
                consumption=r["consumption"],
                interval_start=self._require_datetime(r["interval_start"]),
                interval_end=self._require_datetime(r["interval_end"]),
            )
            for r in results
        ]

    async def get_gas_consumption(
        self,
        mprn: str,
        serial_number: str,
        *,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[Consumption]:
        """Get half-hourly gas consumption readings.

        Args:
            mprn: Meter Point Reference Number.
            serial_number: Meter serial number.
            period_from: Start of period (inclusive).
            period_to: End of period (inclusive).
            page_size: Number of results per page.

        Returns:
            List of consumption readings ordered by interval_start descending.
        """
        path = (
            f"/v1/gas-meter-points/{mprn}"
            f"/meters/{serial_number}/consumption/"
        )
        results = await self._get_paginated(
            path,
            page_size=page_size,
            period_from=period_from,
            period_to=period_to,
        )
        return [
            Consumption(
                consumption=r["consumption"],
                interval_start=self._require_datetime(r["interval_start"]),
                interval_end=self._require_datetime(r["interval_end"]),
            )
            for r in results
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
        ]

    async def get_products(
        self,
        *,
        is_variable: bool | None = None,
        is_business: bool = False,
    ) -> list[Product]:
        """Get available energy products.

        Args:
            is_variable: Filter by variable/fixed. None returns all.
            is_business: Include business products. Defaults to False.

        Returns:
            List of available products.
        """
        params: list[str] = []
        if is_variable is not None:
            params.append(f"is_variable={'true' if is_variable else 'false'}")
        if not is_business:
            params.append("is_business=false")

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
            )
            for r in data.get("results", [])
        ]

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
