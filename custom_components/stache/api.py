"""REST client for the Stache /api/v1 surface (bearer-token auth)."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_V1, CONF_URL

_LOGGER = logging.getLogger(__name__)


class StacheApiError(Exception):
    """Generic REST failure - wraps a server error string when present."""


class StacheAuthError(StacheApiError):
    """401 - the API token was rejected (revoked or wrong)."""


class StacheScopeError(StacheApiError):
    """403 - the token exists but lacks read-write scope."""


class StacheNotFoundError(StacheApiError):
    """404 - the referenced item/area/label doesn't exist."""


class StacheApiClient:
    """Thin async wrapper around Stache's /api/v1 endpoints."""

    def __init__(self, hass: HomeAssistant, base_url: str, token: str) -> None:
        self._session = async_get_clientsession(hass)
        self._base = base_url.rstrip("/") + API_V1
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        data: aiohttp.FormData | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method, url, json=json, data=data, headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise StacheAuthError("API token rejected")
                if resp.status == 403:
                    raise StacheScopeError("token is read-only")
                if resp.status == 404:
                    raise StacheNotFoundError("not found")
                if resp.status == 400:
                    err = await resp.json(content_type=None)
                    raise StacheApiError(err.get("error") or err.get("detail") or "bad request")
                if resp.status >= 400:
                    raise StacheApiError(f"server error {resp.status}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise StacheApiError(f"cannot connect: {err}") from err

    # Reads ---------------------------------------------------------------
    async def areas(self) -> list[dict]:
        return (await self._call("GET", "/areas"))["areas"]

    async def area(self, area_id: str) -> dict:
        return await self._call("GET", f"/areas/{quote(area_id)}")

    async def search(self, query: str) -> list[dict]:
        return (await self._call("GET", f"/items?q={quote(query)}"))["items"]

    async def item(self, item_id: str) -> dict:
        return await self._call("GET", f"/items/{quote(item_id)}")

    async def resolve_label(self, code: str) -> dict:
        return await self._call("GET", f"/labels/{quote(code.upper())}")

    # Writes --------------------------------------------------------------
    async def add_item(
        self,
        *,
        area_id: str | None = None,
        area_label: str | None = None,
        area_name: str | None = None,
        name: str | None = None,
        description: str | None = None,
        quantity: int | None = None,
        barcode: str | None = None,
        tags: list[str] | None = None,
        photo: bytes | None = None,
        photo_name: str = "photo.jpg",
        photo_url: str | None = None,
    ) -> dict:
        if photo is not None:
            form = aiohttp.FormData()
            for k, v in {
                "area_id": area_id, "area_label": area_label, "area_name": area_name,
                "name": name, "description": description, "quantity": quantity,
                "barcode": barcode,
            }.items():
                if v is not None:
                    form.add_field(k, str(v))
            if tags:
                for t in tags:
                    form.add_field("tags", t)
            form.add_field("photo", photo, filename=photo_name)
            return await self._call("POST", "/items", data=form)
        payload = {
            k: v for k, v in {
                "area_id": area_id, "area_label": area_label, "area_name": area_name,
                "name": name, "description": description, "quantity": quantity,
                "barcode": barcode, "tags": tags, "photo_url": photo_url,
            }.items() if v is not None
        }
        return await self._call("POST", "/items", json=payload)

    async def update_item(self, item_id: str, **fields) -> dict:
        payload = {k: v for k, v in fields.items() if v is not None}
        return await self._call("PATCH", f"/items/{quote(item_id)}", json=payload)

    async def move_item(
        self, item_id: str, *, area_id: str | None = None,
        area_label: str | None = None, area_name: str | None = None,
    ) -> dict:
        payload = {k: v for k, v in {
            "area_id": area_id, "area_label": area_label, "area_name": area_name,
        }.items() if v is not None}
        return await self._call("POST", f"/items/{quote(item_id)}/move", json=payload)

    async def validate(self) -> None:
        """Cheap probe - raises StacheAuthError/StacheApiError on failure."""
        await self._call("GET", "/areas")
