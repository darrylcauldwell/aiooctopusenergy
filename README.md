# aiooctopusenergy

Async Python client for the [Octopus Energy REST and GraphQL APIs](https://developer.octopus.energy/docs/api/).

## Installation

```bash
pip install aiooctopusenergy
```

## Usage

### REST client

```python
import aiohttp
from aiooctopusenergy import OctopusEnergyClient

async with aiohttp.ClientSession() as session:
    client = OctopusEnergyClient(api_key="sk_live_...", session=session)

    # Get account details
    account = await client.get_account("A-AAAA1111")
    for prop in account.properties:
        for meter in prop.electricity_meter_points:
            print(f"MPAN: {meter.mpan}, Export: {meter.is_export}")

    # Get half-hourly consumption
    readings = await client.get_electricity_consumption(
        mpan="1100009640372",
        serial_number="22L4344979",
    )
    for r in readings:
        print(f"{r.interval_start}: {r.consumption} kWh")

    # Get Agile rates (no auth required)
    rates = await client.get_electricity_rates(
        product_code="AGILE-24-10-01",
        tariff_code="E-1R-AGILE-24-10-01-C",
    )
    for rate in rates:
        print(f"{rate.valid_from}: {rate.value_inc_vat}p/kWh")

    # Look up Grid Supply Point
    gsps = await client.get_grid_supply_points("DE45")
    print(f"Region: {gsps[0].group_id}")
```

### GraphQL client

```python
from datetime import UTC, datetime, timedelta
from aiooctopusenergy import OctopusEnergyGraphQLClient

async with aiohttp.ClientSession() as session:
    gql = OctopusEnergyGraphQLClient(api_key="sk_live_...", session=session)

    # Get actual rates applied to a meter (Relay-paginated)
    rates = await gql.get_applicable_rates(
        "A-AAAA1111", "1100009640372",
        start_at=datetime(2026, 3, 6, 21, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 6, 23, 0, tzinfo=UTC),
    )
    for r in rates:
        print(f"{r.valid_from}: {r.value_inc_vat}p/kWh")

    # Get hourly solar generation estimates for a postcode
    estimates = await gql.get_solar_generation_estimate("DE45 1AB")
    for e in estimates:
        print(f"{e.date} hour {e.hour}: {e.value} kWh")

    # Get smart tariff cost comparison
    comparison = await gql.get_smart_tariff_comparison(account_number="A-AAAA1111")
    print(f"Current cost: £{comparison['current_cost']}")
    for c in comparison["comparisons"]:
        print(f"  {c.product_code}: £{c.cost_inc_vat}")

    # Live readings from an Octopus Home Mini
    devices = await gql.get_smart_meter_devices("A-AAAA1111")
    end = datetime.now(UTC)
    readings = await gql.get_smart_meter_telemetry(
        devices[0].device_id, start=end - timedelta(minutes=2), end=end
    )
    print(f"Demand now: {readings[-1].demand_w} W")
```

## API Reference

### `OctopusEnergyClient(api_key, session=None)`

REST client. Can be used as an async context manager or with an existing session.

- `get_account(account_number)` — Account details with meters and tariff history
- `get_electricity_consumption(mpan, serial, *, period_from, period_to, page_size, page_delay)` — Half-hourly electricity readings
- `get_gas_consumption(mprn, serial, *, period_from, period_to)` — Half-hourly gas readings
- `get_electricity_rates(product, tariff, *, period_from, period_to)` — Electricity unit rates
- `get_electricity_day_rates(product, tariff, *, period_from, period_to)` — Dual-register day rates
- `get_electricity_night_rates(product, tariff, *, period_from, period_to)` — Dual-register night rates
- `get_electricity_standing_charges(product, tariff, *, period_from, period_to)` — Electricity standing charges
- `get_gas_rates(product, tariff, *, period_from, period_to)` — Gas unit rates
- `get_gas_standing_charges(product, tariff, *, period_from, period_to)` — Gas standing charges
- `get_grid_supply_points(postcode)` — GSP region lookup

The `page_delay` parameter (float, seconds) adds a delay between paginated API calls to avoid rate limits. Defaults to `0.0`.

### `OctopusEnergyGraphQLClient(api_key, session=None)`

GraphQL client with JWT authentication. Can be used as an async context manager.

- `get_applicable_rates(account_number, mpxn, *, start_at, end_at)` — Actual rates applied to a meter (Relay-paginated)
- `get_solar_generation_estimate(postcode, *, from_date)` — Hourly solar generation estimates
- `get_smart_tariff_comparison(*, account_number, mpan)` — Tariff cost comparison
- `get_smart_meter_devices(account_number)` — Active smart import electricity meters and their device IDs
- `get_smart_meter_telemetry(device_id, *, start, end, grouping)` — Home Mini readings (demand in W, consumption in kWh); `grouping` is one of `TEN_SECONDS`, `ONE_MINUTE`, `FIVE_MINUTES`, `HALF_HOURLY`, `HOURLY`

### Exceptions

- `OctopusEnergyError` — Base exception
- `OctopusEnergyAuthenticationError` — Invalid API key (HTTP 401)
- `OctopusEnergyNotFoundError` — Resource not found (HTTP 404)
- `OctopusEnergyRateLimitError` — Rate limited (HTTP 429)
- `OctopusEnergyConnectionError` — Network error
- `OctopusEnergyTimeoutError` — Request timeout

## License

MIT
