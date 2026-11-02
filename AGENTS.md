# stache-ha

HACS custom integration exposing [Stache](https://github.com/GraphicHealer/Stache)
inventory state as Home Assistant sensors. Sibling repos: `../Stache` (the app -
source of the API contract) and `../stache-site` (marketing/docs).

## Stack

- Pure Python custom component in `custom_components/stache/` - no deps
  (`requirements: []` in `manifest.json`), just HA's bundled aiohttp +
  voluptuous. Domain: `stache`, `integration_type: hub`, `local_polling`.
- Distributed via HACS (`hacs.json`, min HA `2025.1.0` - relies on
  `runtime_data`, modern `OptionsFlow`, coordinator `config_entry=`).
  Version lives in `manifest.json` only - bump it per release.
- `.github/workflows/validate.yml` runs hassfest + the HACS action on
  push/PR. Local check: `python -m compileall custom_components/`.

## Shape

- `config_flow.py` - accepts either the pasted out-sensor URL (splits host +
  token itself via `parse_input`) or base URL + token fields. Validates with
  a live GET (`_validate`) before creating the entry. `unique_id` = base URL.
  Also hosts `async_step_reauth`/`reauth_confirm` (token-only) and
  `StacheOptionsFlow` (poll interval, 30-3600s, default 120).
- `coordinator.py` - `StacheConfigEntry` type alias + one
  `DataUpdateCoordinator` polling
  `GET {base}/api/webhooks/out-sensor?token={token}`. 401 raises
  `ConfigEntryAuthFailed` (triggers the reauth flow); other failures raise
  `UpdateFailed`. Uses HA's shared `async_get_clientsession`.
- `sensor.py` - sensors are `StacheSensorEntityDescription`s in the
  `SENSORS` tuple (key, translation_key, `value_fn`, `attributes_fn`); add a
  sensor by appending one entry. Icons live in `icons.json`, names in
  `strings.json`/`translations/en.json`.
- `__init__.py` - stashes the coordinator in `entry.runtime_data`
  (typed `ConfigEntry`, no `hass.data`), reloads on options change via
  `add_update_listener`.
- `diagnostics.py` - dumps entry + coordinator data, redacts `token`.

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
changes server-side, update the `SENSORS` value/attributes fns here to match.

## Conventions & gotchas

- **Auth** is the `settings.webhook_token` query param - session-exempt on the
  server but 401s without it. A 401 during polling raises
  `ConfigEntryAuthFailed`, which kicks off `reauth_confirm` automatically -
  never swallow it into `UpdateFailed`.
- **Entry compat**: `entry.data` keys (`url`, `token`) and `unique_id` (base
  URL) are stable - existing installs upgrade without a migration. Don't
  rename them; bump `ConfigFlow.VERSION` + write a migration if they must
  change.
- **Privacy**: the server filters to shared items only - `is_private` items are
  never in the payload, so there's nothing extra to do here. Keep it that way.
- **`parse_input` only extracts the token** when the pasted path ends with
  `/api/webhooks/out-sensor`; a pasted base URL keeps the separate token field.
- **Attributes are capped** at `MAX_ATTR_ITEMS = 50` - HA recorder chokes on
  giant attribute lists.
- Token is stored in `entry.data` (plaintext, like every HA custom integration)
  - never log it; `diagnostics.py` redacts it via `TO_REDACT`.
- `from __future__ import annotations` + full type hints, matching HA core
  style. Entities use `_attr_has_entity_name = True` + `translation_key`s -
  user-facing strings belong in `strings.json`/`translations/en.json`, icons
  in `icons.json`, not hardcoded `_attr_icon`/`_attr_name`.
