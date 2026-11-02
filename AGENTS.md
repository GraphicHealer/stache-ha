# stache-ha

HACS custom integration exposing [Stache](https://github.com/GraphicHealer/Stache)
inventory state as Home Assistant sensors. Sibling repos: `../Stache` (the app -
source of the API contract) and `../stache-site` (marketing/docs).

## Stack

- Pure Python custom component in `custom_components/stache/` - no deps
  (`requirements: []` in `manifest.json`), just HA's bundled aiohttp +
  voluptuous. Domain: `stache`, `integration_type: hub`, `local_polling`.
- Distributed via HACS (`hacs.json`, min HA `2024.6.0`). Version lives in
  `manifest.json` only - bump it per release.
- No tests, CI, or lint config yet. Validate by dropping the component into a
  dev HA instance's `custom_components/` and reloading.

## Shape

- `config_flow.py` - accepts either the pasted out-sensor URL (splits host +
  token itself via `parse_input`) or base URL + token fields. Validates with a
  live GET before creating the entry. `unique_id` = base URL.
- `coordinator.py` - one `DataUpdateCoordinator` polling
  `GET {base}/api/webhooks/out-sensor?token={token}` every
  `DEFAULT_SCAN_INTERVAL` (120s). Uses HA's shared `async_get_clientsession`.
- `sensor.py` - four sensors driven by the `DESCRIPTIONS` table; add a sensor
  by appending a row, no other wiring needed.
- `__init__.py` - stashes the coordinator in
  `hass.data[DOMAIN][entry.entry_id]`, forwards to `Platform.SENSOR`.

## The contract (server side is `server/src/routes/out.ts` in Stache)

`out-sensor` returns:

```json
{
  "out_count": 3,
  "unaccounted_count": 1,
  "total": 4,
  "items": [{ "name": "...", "path": "...", "days": 5 }],
  "low_stock_count": 2,
  "low_stock": [{ "name": "...", "quantity": 1, "restock_below": 2 }],
  "warranty_expiring": [{ "name": "...", "warranty_until": "2026-12-01" }]
}
```

`items` is out + unaccounted **combined** (unaccounted has no list of its own).
Warranty sensor has no count field - it counts the list. If the payload shape
changes server-side, update `DESCRIPTIONS` keys here to match.

## Conventions & gotchas

- **Auth** is the `settings.webhook_token` query param - session-exempt on the
  server but 401s without it. `invalid_auth` on 401, `cannot_connect` on
  anything else (DNS, timeout, non-OK).
- **Privacy**: the server filters to shared items only - `is_private` items are
  never in the payload, so there's nothing extra to do here. Keep it that way.
- **`parse_input` only extracts the token** when the pasted path ends with
  `/api/webhooks/out-sensor`; a pasted base URL keeps the separate token field.
- **Attributes are capped** at `MAX_ATTR_ITEMS = 50` - HA recorder chokes on
  giant attribute lists.
- Token is stored in `entry.data` (plaintext, like every HA custom integration)
  - never log it, never put it in diagnostics output.
- `from __future__ import annotations` + full type hints, matching HA core
  style. Entities use `_attr_has_entity_name = True` + `translation_key`s -
  user-facing strings belong in `strings.json`/`translations/en.json`, not
  hardcoded.
