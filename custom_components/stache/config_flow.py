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
    CONF_API_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SENSOR_PATH,
)
from .api import StacheApiClient, StacheApiError, StacheAuthError
from .coordinator import StacheConfigEntry, sensor_url, valid_payload

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_TOKEN): str,
        # Optional - enables the services. Leave empty for sensors only.
        vol.Optional(CONF_API_TOKEN): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})
RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


async def _validate_api(hass, url: str, api_token: str) -> str | None:
    """Probe /api/v1 with the bearer token; return an error key or None."""
    try:
        await StacheApiClient(hass, url, api_token).validate()
    except StacheAuthError:
        return "invalid_api_token"
    except StacheApiError:
        return "cannot_connect_api"
    return None


def parse_input(url: str, token: str | None) -> tuple[str, str | None]:
    """Split a pasted out-sensor URL into base + token, or keep them as given.

    Raises ValueError("invalid_url") on malformed input - the flow maps it to
    a field error rather than letting urlparse exceptions escape.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError as err:
        raise ValueError("invalid_url") from err
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("invalid_url")
    if parsed.path.rstrip("/").endswith(SENSOR_PATH):
        params = parse_qs(parsed.query)
        # Only the token param is expected; fragments or other params would
        # corrupt the endpoint we rebuild - reject rather than silently drop.
        if parsed.fragment or set(params) - {"token"}:
            raise ValueError("invalid_url")
        tokens = params.get("token", [])
        if len(tokens) > 1:
            raise ValueError("invalid_url")  # ambiguous - refuse silently picking one
        token = tokens[0] if tokens else token
        # Strip only the sensor endpoint - keep any reverse-proxy path prefix.
        prefix = parsed.path.rstrip("/")[: -len(SENSOR_PATH)]
        base = urlunparse((parsed.scheme, parsed.netloc, prefix, "", "", ""))
    else:
        # A base URL may carry a path prefix (reverse proxy) but never a
        # query string or fragment - they'd corrupt the endpoint we build.
        if parsed.query or parsed.fragment:
            raise ValueError("invalid_url")
        base = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", "")
        )
    return base.rstrip("/"), token


async def _validate(hass, url: str, token: str) -> str | None:
    """Probe the sensor endpoint; return an error key or None on success."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            sensor_url(url, token), timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 401:
                return "invalid_auth"
            if resp.status != 200:
                return "cannot_connect"
            try:
                data = await resp.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                # Server answered but the body isn't JSON we can use - that
                # is a wrong-service problem, not a connectivity one.
                return "invalid_response"
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"
    if not valid_payload(data):
        return "invalid_response"
    return None


class StacheConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url, token = parse_input(
                    user_input[CONF_URL], user_input.get(CONF_TOKEN) or None
                )
            except ValueError:
                errors[CONF_URL] = "invalid_url"
                return self.async_show_form(
                    step_id="user", data_schema=USER_SCHEMA, errors=errors
                )
            if not token:
                errors["base"] = "token_required"
            elif (error := await _validate(self.hass, url, token)) is not None:
                errors["base"] = error
            else:
                api_token = (user_input.get(CONF_API_TOKEN) or "").strip() or None
                if api_token and (
                    api_error := await _validate_api(self.hass, url, api_token)
                ) is not None:
                    errors[CONF_API_TOKEN] = api_error
                    return self.async_show_form(
                        step_id="user", data_schema=USER_SCHEMA, errors=errors
                    )
                data = {CONF_URL: url, CONF_TOKEN: token}
                if api_token:
                    data[CONF_API_TOKEN] = api_token
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Stache ({urlparse(url).netloc})",
                    data=data,
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add/replace the REST API token - services need it, sensors don't."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_token = (user_input.get(CONF_API_TOKEN) or "").strip() or None
            if not api_token:
                errors[CONF_API_TOKEN] = "token_required"
            elif (
                error := await _validate_api(
                    self.hass, entry.data[CONF_URL], api_token
                )
            ) is not None:
                errors[CONF_API_TOKEN] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: api_token}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=RECONFIGURE_SCHEMA,
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
