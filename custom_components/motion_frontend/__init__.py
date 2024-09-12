"""The Motion Frontend integration."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import types
import typing

import aiohttp
from homeassistant.components import webhook
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from homeassistant.util import raise_if_invalid_path

from .camera import MotionFrontendCamera
from .const import (
    CONF_MEDIASOURCE,
    CONF_OPTION_AUTO,
    CONF_OPTION_CLOUD,
    CONF_OPTION_DEFAULT,
    CONF_OPTION_EXTERNAL,
    CONF_OPTION_FORCE,
    CONF_OPTION_INTERNAL,
    CONF_OPTION_NONE,
    CONF_TLS_MODE,
    CONF_WEBHOOK_ADDRESS,
    CONF_WEBHOOK_MODE,
    DOMAIN,
    EXTRA_ATTR_FILENAME,
    MANAGED_EVENTS,
    MAP_TLS_MODE,
    PLATFORMS,
)
from .helpers import LOGGER
from .motionclient import (
    MotionHttpClient,
    MotionHttpClientError,
    TlsMode,
    config_schema as cs,
)

if typing.TYPE_CHECKING:
    import aiohttp.web
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from .alarm_control_panel import MotionFrontendAlarmControlPanel


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    data = config_entry.data

    api = MotionFrontendApi(hass, data)
    try:
        await api.update(updatecameras=True)
    except MotionHttpClientError as err:
        await api.close()
        raise ConfigEntryNotReady from err

    if not api.is_available:
        raise ConfigEntryNotReady

    api.unsub_entry_update_listener = config_entry.add_update_listener(
        api.entry_update_listener
    )

    hass.data[DOMAIN][config_entry.entry_id] = api

    webhook_mode = data.get(CONF_WEBHOOK_MODE)
    if webhook_mode != CONF_OPTION_NONE:
        # setup webhook to manage 'push' from motion server
        try:
            webhook_id = f"{DOMAIN}_{config_entry.entry_id}"
            webhook.async_register(
                hass, DOMAIN, DOMAIN, webhook_id, api.async_handle_webhook
            )
            api.webhook_id = (
                webhook_id  # set here after succesfully calling async_register
            )
            webhook_address = data.get(CONF_WEBHOOK_ADDRESS, CONF_OPTION_DEFAULT)
            if webhook_address == CONF_OPTION_INTERNAL:
                api.webhook_url = get_url(
                    hass, allow_internal=True, allow_external=False, allow_cloud=False
                )
            elif webhook_address == CONF_OPTION_EXTERNAL:
                api.webhook_url = get_url(
                    hass,
                    allow_internal=False,
                    allow_external=True,
                    allow_cloud=True,
                    prefer_cloud=False,
                )
            elif webhook_address == CONF_OPTION_CLOUD:
                api.webhook_url = get_url(
                    hass,
                    allow_internal=False,
                    allow_external=False,
                    allow_cloud=True,
                    prefer_cloud=True,
                )
            else:
                api.webhook_url = get_url(hass)
            api.webhook_url += webhook.async_generate_path(api.webhook_id)

            force = webhook_mode == CONF_OPTION_FORCE

            config = api.config
            for event in MANAGED_EVENTS:
                hookcommand = (
                    f"curl%20-d%20'event={event}'%20"
                    "-d%20'camera_id=%t'%20"
                    "-d%20'event_id=%v'%20"
                    "-d%20'filename=%f'%20"
                    "-d%20'filetype=%n'%20"
                    f"{api.webhook_url}"
                )

                command = config.get(event)
                if (command != hookcommand) and (force or (command is None)):
                    await api.async_config_set(event, hookcommand)

            LOGGER.info("Registered webhook for motion events")
        except Exception as exception:
            LOGGER.exception("exception (%s) setting up webhook", str(exception))
            if api.webhook_id:
                webhook.async_unregister(
                    hass, api.webhook_id
                )  # this is actually 'safe'
                api.webhook_id = None
                api.webhook_url = None

    # setup media_source entry to access server recordings if they're local
    if data.get(CONF_MEDIASOURCE):
        try:
            media_dir_id = f"{DOMAIN}_{api.unique_id}"
            if media_dir_id not in hass.config.media_dirs:
                target_dir: str | None = api.config.get(cs.TARGET_DIR)  # type: ignore
                if target_dir:
                    raise_if_invalid_path(target_dir)
                    if os.access(target_dir, os.R_OK):
                        hass.config.media_dirs[media_dir_id] = target_dir
                        LOGGER.info(
                            "Registered media_dirs[%s] for motion server target_dir",
                            media_dir_id,
                        )
                        api.media_dir_id = media_dir_id
                    else:
                        LOGGER.error(
                            "Missing read access for target recordings directory"
                        )

        except Exception as err:
            LOGGER.exception(
                "exception (%s) setting up media_source directory", str(err)
            )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):

    if await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        hassdata = hass.data[DOMAIN]
        api: MotionFrontendApi = hassdata[config_entry.entry_id]
        await api.close()
        if api.webhook_id:
            webhook.async_unregister(hass, api.webhook_id)
            api.webhook_id = None
        if api.media_dir_id:
            try:  # better be safe...
                hass.config.media_dirs.pop(api.media_dir_id, None)
            except:
                pass
        if api.unsub_entry_update_listener:
            api.unsub_entry_update_listener()
            api.unsub_entry_update_listener = None
        hassdata.pop(config_entry.entry_id)
        return True

    return False


class MotionFrontendApi(MotionHttpClient):
    cameras: dict[str, MotionFrontendCamera]

    def __init__(
        self, hass: HomeAssistant, data: types.MappingProxyType[str, typing.Any]
    ):
        self.hass = hass
        self.config_data = data
        self.webhook_id: str | None = None
        self.webhook_url: str | None = None
        self.media_dir_id: str | None = None
        self.unsub_entry_update_listener: CALLBACK_TYPE | None = None
        self.alarm_control_panel: MotionFrontendAlarmControlPanel | None = None
        MotionHttpClient.__init__(
            self,
            data[CONF_HOST],
            data[CONF_PORT],
            username=data.get(CONF_USERNAME),
            password=data.get(CONF_PASSWORD),
            tlsmode=MAP_TLS_MODE.get(
                data.get(CONF_TLS_MODE, CONF_OPTION_AUTO), TlsMode.AUTO
            ),
            session=async_get_clientsession(hass),
            logger=LOGGER,
            camera_factory=_entity_camera_factory,  # type: ignore
        )

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "motion-project.github.io",
            "sw_version": self.version,
        }

    async def async_handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: aiohttp.web.Request
    ):
        try:
            async with asyncio.timeout(5):
                data = dict(await request.post())

            LOGGER.debug("Received webhook - (%s)", data)

            camera = typing.cast(
                MotionFrontendCamera, self.getcamera(str(data["camera_id"]))
            )
            if self.media_dir_id:
                try:  # fix the path as a media_source compatible url
                    filename = data.get(EXTRA_ATTR_FILENAME)
                    if filename:
                        filename = Path(str(filename)).relative_to(
                            str(self.config[cs.TARGET_DIR])
                        )
                        data[EXTRA_ATTR_FILENAME] = (
                            f"{self.media_dir_id}/{str(filename)}"
                        )
                except:
                    pass
            camera.handle_event(data)

        except Exception as exception:
            LOGGER.error(
                "async_handle_webhook - %s(%s)",
                exception.__class__.__name__,
                str(exception),
            )

    @callback
    async def entry_update_listener(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)
        return

    def notify_state_changed(self, camera: MotionFrontendCamera):
        """
        called by cameras to synchronously update alarm panel
        """
        if self.alarm_control_panel:
            self.alarm_control_panel.notify_state_changed(camera)


def _entity_camera_factory(client: MotionFrontendApi, id: str):
    return MotionFrontendCamera(client, id)
