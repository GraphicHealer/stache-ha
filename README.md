<p align="center">
  <img src="https://raw.githubusercontent.com/GraphicHealer/Stache/main/client/public/icon.svg" alt="Stache logo" width="128">
</p>
<h1 align="center">Stache for Home Assistant</h1>
<p align="center">
  Exposes what's out of place, running low, or nearing the end of warranty in
  <a href="https://github.com/GraphicHealer/Stache">Stache</a> as Home Assistant sensors -
  plus services that search and manage inventory directly from automations.
</p>
<p align="center">
  <a href="AI-DECLARATION.md"><img src="https://img.shields.io/badge/AI--DECLARATION-pair-blue" alt="AI-DECLARATION: pair"></a>
</p>
<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=GraphicHealer&repository=stache-ha&category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open in HACS"></a>
  <a href="https://github.com/GraphicHealer/stache-ha/actions/workflows/validate.yml"><img src="https://github.com/GraphicHealer/stache-ha/actions/workflows/validate.yml/badge.svg" alt="Validate"></a>
</p>

## Services

When the entry also has an **API token** (Stache Settings -> API tokens - paste it
into the integration's **Reconfigure** step for existing installs, or the initial
setup for new ones), these services appear under `stache.*`:

| Service | What it does |
|---------|-------------|
| `stache.search` | Search shared items - returns `items` |
| `stache.add_item` | File a new item - `area_id`/`area_label`/`area_name`, optional `name`, `description`, `quantity`, `barcode`, `tags`, `photo_path` (allowlisted dir) or `photo_url` |
| `stache.update_item` | Patch fields and/or status on an item |
| `stache.set_status` | Set an item's status (`home`/`out`/`lent`/`unaccounted`/`gone`) |
| `stache.move_item` | Move an item to a different area |
| `stache.resolve_label` | Resolve a QR label code to its area |

All services return response data usable in automations (e.g.
`{{ items[0].id }}` from `stache.search`). Writes go through the same event
pipeline as the app - undo works in Stache as usual.

## Install

Requires Home Assistant **2025.1** or newer.

1. Click the HACS badge above (or add `https://github.com/GraphicHealer/stache-ha` as a
   custom repository in HACS, category: Integration).
2. Install **Stache** from HACS, restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> **Stache**.

## Configure

The integration needs one thing: the sensor URL from Stache.

1. In Stache, go to **Settings -> Out reminders**, enable it if it is off, and press
   **Copy sensor URL**.
2. Paste the whole URL into the setup dialog. The integration splits out the host
   and token itself.

You can also enter the Stache URL (`http://homeassistant.local:8080`, or your
server's address) and the webhook token as two fields.

## Sensors

| Sensor | State | Attributes |
|--------|-------|------------|
| Items out | Count of things marked out/lent | Item names, area paths, days out |
| Unaccounted | Count of items nobody has seen lately | - |
| Low stock | Count of items at/below their restock point | Names, quantity, threshold |
| Warranty expiring | Count of warranties ending within 30 days | Names, end dates |

Polls every 2 minutes by default (change it under the integration's
**Configure** options). All shared household items are included; private items
are never exposed. If the stored token is ever rejected, Home Assistant raises
a repair asking for a fresh one.

## Example automation

```yaml
alias: Stuff still out tonight
triggers:
  - trigger: time
    at: "21:00:00"
conditions:
  - condition: numeric_state
    entity_id: sensor.stache_items_out
    above: 0
actions:
  - action: notify.notify
    data:
      title: Stache
      message: "{{ states('sensor.stache_items_out') }} things are still out."
```

Stache also exposes a POST webhook (`.../api/webhooks/digest?token=...`) that
sends the bundled digest on demand - call it from an HA `rest_command` if you
want the digest pushed at a specific time.

## License

[AGPL-3.0](LICENSE) - forks must stay open source, with attribution.
