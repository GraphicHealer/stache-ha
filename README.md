# Stash for Home Assistant

Home Assistant integration for [Stash](https://github.com/GraphicHealer/Stash) - the
photo-first home inventory. Exposes what's out of place, running low, or nearing
the end of warranty as sensors you can automate on.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=GraphicHealer&repository=stash-ha&category=integration)

## Install

1. Click the badge above (or add `https://github.com/GraphicHealer/stash-ha` as a
   custom repository in HACS, category: Integration).
2. Install **Stash** from HACS, restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> **Stash**.

## Configure

The integration needs one thing: the sensor URL from Stash.

1. In Stash, go to **Settings -> Out reminders**, enable it if it is off, and press
   **Copy sensor URL**.
2. Paste the whole URL into the setup dialog. The integration splits out the host
   and token itself.

You can also enter the Stash URL (`http://homeassistant.local:8080`, or your
server's address) and the webhook token as two fields.

## Sensors

| Sensor | State | Attributes |
|--------|-------|------------|
| Items out | Count of things marked out/lent | Item names, area paths, days out |
| Unaccounted | Count of items nobody has seen lately | - |
| Low stock | Count of items at/below their restock point | Names, quantity, threshold |
| Warranty expiring | Count of warranties ending within 30 days | Names, end dates |

Polls every 2 minutes. All shared household items are included; private items
are never exposed.

## Example automation

```yaml
alias: Stuff still out tonight
triggers:
  - trigger: time
    at: "21:00:00"
conditions:
  - condition: numeric_state
    entity_id: sensor.stash_items_out
    above: 0
actions:
  - action: notify.notify
    data:
      title: Stash
      message: "{{ states('sensor.stash_items_out') }} things are still out."
```

Stash also exposes a POST webhook (`.../api/webhooks/digest?token=...`) that
sends the bundled digest on demand - call it from an HA `rest_command` if you
want the digest pushed at a specific time.
