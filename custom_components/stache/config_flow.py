"""Config flow for Stache - accepts a pasted sensor URL or host + token."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SENSOR_PATH,
)
from .coordinator import StacheConfigEntry, sensor_url

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_TOKEN): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


def parse_input(url: str, token: str | None) -> tuple[str, str | None]:
    """Split a pasted out-sensor URL into base + token, or keep them as given."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.path.rstrip("/").endswith(SENSOR_PATH):
        token = parse_qs(parsed.query).get("token", [token])[0]
        url = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return url.rstrip("/"), token


async def _validate(hass, url: str, token: str) -> str | None:
    """Probe the sensor endpoint; return an error key or None on success."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            sensor_url(url, token), timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 401:
                return "invalid_auth"
            if not resp.ok:
                return "cannot_connect"
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"
    return None


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
            elif (error := await _validate(self.hass, url, token)) is not None:
                errors["base"] = error
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Stache ({urlparse(url).netloc})",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = (user_input.get(CONF_TOKEN) or "").strip() or None
            if not token:
                errors["base"] = "token_required"
            elif (
                error := await _validate(self.hass, entry.data[CONF_URL], token)
            ) is not None:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: StacheConfigEntry) -> StacheOptionsFlow:
        return StacheOptionsFlow()


class StacheOptionsFlow(OptionsFlow):
    """Polling interval option."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL
                        ),
                    )
                }
            ),
        )
