"""HA services for the Stache integration - read and write inventory."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError

from .api import StacheApiClient, StacheApiError, StacheAuthError
from .const import (
    CONF_API_TOKEN,
    CONF_URL,
    DOMAIN,
    SERVICE_ADD_ITEM,
    SERVICE_MOVE_ITEM,
    SERVICE_RESOLVE_LABEL,
    SERVICE_SEARCH,
    SERVICE_SET_STATUS,
    SERVICE_UPDATE_ITEM,
)

_LOGGER = logging.getLogger(__name__)

AREA_REF_SCHEMA = {
    vol.Exclusive("area_id", "area"): str,
    vol.Exclusive("area_label", "area"): str,
    vol.Exclusive("area_name", "area"): str,
}

STATUS_CHOICES = ["home", "out", "lent", "unaccounted", "gone"]

# Server upload cap is 25MB - reject oversize photos before reading them.
MAX_PHOTO_BYTES = 25 * 1024 * 1024

SEARCH_SCHEMA = vol.Schema({vol.Required("query"): cv.string})

ADD_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("name"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("quantity"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000000)),
        vol.Optional("barcode"): cv.string,
        vol.Optional("tags"): vol.All(cv.ensure_list, [cv.string]),
        vol.Exclusive("photo_path", "photo"): cv.string,
        vol.Exclusive("photo_url", "photo"): cv.url,
        **AREA_REF_SCHEMA,
    }
)

UPDATE_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Optional("name"): vol.Any(None, cv.string),
        vol.Optional("description"): vol.Any(None, cv.string),
        vol.Optional("quantity"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000000)),
        vol.Optional("barcode"): vol.Any(None, cv.string),
        vol.Optional("tags"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("status"): vol.In(STATUS_CHOICES),
        vol.Optional("lent_to"): vol.Any(None, cv.string),
    }
)

SET_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Required("status"): vol.In(STATUS_CHOICES),
        vol.Optional("lent_to"): cv.string,
    }
)

MOVE_ITEM_SCHEMA = vol.Schema({vol.Required("item_id"): cv.string, **AREA_REF_SCHEMA})

RESOLVE_LABEL_SCHEMA = vol.Schema({vol.Required("code"): cv.string})


def _client(hass: HomeAssistant) -> StacheApiClient:
    """Resolve the first configured entry's API client."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        data = getattr(entry, "runtime_data", None)
        client = getattr(data, "api", None)
        if client is not None:
            return client
        if entry.data.get(CONF_API_TOKEN):
            return StacheApiClient(hass, entry.data[CONF_URL], entry.data[CONF_API_TOKEN])
    raise ServiceValidationError(
        "No Stache API token configured - create one in Stache Settings -> "
        "API tokens and add it via the integration's reconfigure step."
    )


def _area_kwargs(call: ServiceCall) -> dict[str, Any]:
    return {
        k: call.data.get(k) for k in ("area_id", "area_label", "area_name")
        if call.data.get(k)
    }


async def _photo(call: ServiceCall) -> bytes | None:
    """Read a photo file the HA host can see (allowlist_external_dirs)."""
    path = call.data.get("photo_path")
    if not path:
        return None
    hass = call.hass
    if not hass.config.is_allowed_path(path):
        raise ServiceValidationError(
            f"'{path}' is not in an allowlisted external directory - add it to "
            "allowlist_external_dirs in configuration.yaml."
        )
    try:
        size = (await hass.async_add_executor_job(Path(path).stat)).st_size
    except OSError as err:
        raise ServiceValidationError(f"could not read photo_path: {err}") from err
    if size > MAX_PHOTO_BYTES:
        raise ServiceValidationError(
            f"photo_path is {size // 1024 // 1024}MB - the limit is 25MB."
        )
    try:
        return await hass.async_add_executor_job(Path(path).read_bytes)
    except OSError as err:
        raise ServiceValidationError(f"could not read photo_path: {err}") from err


def _translate(e: Exception) -> ServiceValidationError:
    return ServiceValidationError(str(e))


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the domain services once."""

    async def search(call: ServiceCall) -> dict[str, Any]:
        try:
            items = await _client(hass).search(call.data["query"])
        except StacheApiError as e:
            raise _translate(e) from e
        return {"items": items}

    async def add_item(call: ServiceCall) -> dict[str, Any]:
        photo = await _photo(call)
        kwargs = {
            "name": call.data.get("name"),
            "description": call.data.get("description"),
            "quantity": call.data.get("quantity"),
            "barcode": call.data.get("barcode"),
            "tags": call.data.get("tags"),
            "photo": photo,
            "photo_url": call.data.get("photo_url"),
        }
        kwargs.update(_area_kwargs(call))
        try:
            res = await _client(hass).add_item(**kwargs)
        except StacheApiError as e:
            raise _translate(e) from e
        return {"item": res.get("item"), "event_id": res.get("event_id")}

    async def update_item(call: ServiceCall) -> dict[str, Any]:
        fields = {
            k: call.data.get(k)
            for k in ("name", "description", "quantity", "barcode", "tags", "status", "lent_to")
            if call.data.get(k) is not None
        }
        if not fields:
            raise ServiceValidationError("nothing to update - pass at least one field")
        try:
            res = await _client(hass).update_item(call.data["item_id"], **fields)
        except StacheApiError as e:
            raise _translate(e) from e
        return {"item": res.get("item"), "event_ids": res.get("event_ids")}

    async def set_status(call: ServiceCall) -> dict[str, Any]:
        fields = {"status": call.data["status"]}
        if call.data.get("lent_to"):
            fields["lent_to"] = call.data["lent_to"]
        try:
            res = await _client(hass).update_item(call.data["item_id"], **fields)
        except StacheApiError as e:
            raise _translate(e) from e
        return {"item": res.get("item"), "event_ids": res.get("event_ids")}

    async def move_item(call: ServiceCall) -> dict[str, Any]:
        kwargs = _area_kwargs(call)
        if not kwargs:
            raise ServiceValidationError("pass area_id, area_label, or area_name")
        try:
            res = await _client(hass).move_item(call.data["item_id"], **kwargs)
        except StacheApiError as e:
            raise _translate(e) from e
        return {"ok": res.get("ok"), "event_id": res.get("event_id")}

    async def resolve_label(call: ServiceCall) -> dict[str, Any]:
        try:
            res = await _client(hass).resolve_label(call.data["code"])
        except StacheApiError as e:
            raise _translate(e) from e
        return {"label": res.get("label"), "area": res.get("area")}

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH, search, schema=SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_ITEM, add_item, schema=ADD_ITEM_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_ITEM, update_item, schema=UPDATE_ITEM_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_STATUS, set_status, schema=SET_STATUS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MOVE_ITEM, move_item, schema=MOVE_ITEM_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESOLVE_LABEL, resolve_label, schema=RESOLVE_LABEL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
