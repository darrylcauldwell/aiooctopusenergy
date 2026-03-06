# aiooctopusenergy

Async Python client for the [Octopus Energy REST API](https://developer.octopus.energy/docs/api/).

## Installation

```bash
pip install aiooctopusenergy
```

## Usage

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

## API Reference

### `OctopusEnergyClient(api_key, session=None)`

- `get_account(account_number)` — Account details with meters and tariff history
- `get_electricity_consumption(mpan, serial, *, period_from, period_to)` — Half-hourly electricity readings
- `get_gas_consumption(mprn, serial, *, period_from, period_to)` — Half-hourly gas readings
- `get_electricity_rates(product, tariff, *, period_from, period_to)` — Electricity unit rates
- `get_electricity_standing_charges(product, tariff, *, period_from, period_to)` — Electricity standing charges
- `get_gas_rates(product, tariff, *, period_from, period_to)` — Gas unit rates
- `get_gas_standing_charges(product, tariff, *, period_from, period_to)` — Gas standing charges
- `get_grid_supply_points(postcode)` — GSP region lookup

### Exceptions

- `OctopusEnergyError` — Base exception
- `OctopusEnergyAuthenticationError` — Invalid API key (HTTP 401)
- `OctopusEnergyNotFoundError` — Resource not found (HTTP 404)
- `OctopusEnergyConnectionError` — Network error
- `OctopusEnergyTimeoutError` — Request timeout

## License

MIT
