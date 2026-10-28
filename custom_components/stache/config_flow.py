"""Config flow for Stache - accepts a pasted sensor URL or host + token."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOKEN, CONF_URL, DOMAIN, SENSOR_PATH
from .coordinator import sensor_url

_LOGGER = logging.getLogger(__name__)


def parse_input(url: str, token: str | None) -> tuple[str, str | None]:
    """Split a pasted out-sensor URL into base + token, or keep them as given."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.path.rstrip("/").endswith(SENSOR_PATH):
        token = parse_qs(parsed.query).get("token", [token])[0]
        url = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return url.rstrip("/"), token


class StacheConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url, token = parse_input(
                user_input[CONF_URL], user_input.get(CONF_TOKEN) or None
            )
            if not token:
                errors["base"] = "token_required"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    async with session.get(
                        sensor_url(url, token), timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 401:
                            errors["base"] = "invalid_auth"
                        elif not resp.ok:
                            errors["base"] = "cannot_connect"
                except Exception:
                    errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Stache ({urlparse(url).netloc})",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Optional(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )
