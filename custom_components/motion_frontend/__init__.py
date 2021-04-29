"""The Motion Frontend integration."""
from typing import Any, Callable, Dict, List, Optional, Union
import asyncio

#from aiohttp.web import Request, Response
import aiohttp
import async_timeout
import os
from pathlib import Path


from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from homeassistant.helpers import device_registry
from homeassistant.util import raise_if_invalid_path
from homeassistant.helpers.aiohttp_client import async_get_clientsession
#from homeassistant.helpers.network import get_url
from homeassistant.const import (
    CONF_HOST, CONF_PORT,
    CONF_USERNAME, CONF_PASSWORD, ATTR_AREA_ID
)

from .motionclient import MotionHttpClient, MotionHttpClientError, MotionHttpClientConnectionError

from .helpers import (
    LOGGER, LOGGER_trap,
)
from logging import WARNING, INFO

from .const import (
    DOMAIN, PLATFORMS,
    CONF_OPTION_NONE, CONF_OPTION_DEFAULT, CONF_OPTION_FORCE, CONF_OPTION_AUTO,
    CONF_TLS_MODE, MAP_TLS_MODE,
    CONF_WEBHOOK_MODE,
    CONF_WEBHOOK_ADDRESS, CONF_OPTION_INTERNAL, CONF_OPTION_EXTERNAL, CONF_OPTION_CLOUD,
    CONF_MEDIASOURCE,
    EXTRA_ATTR_FILENAME,
    MANAGED_EVENTS
)


async def async_setup(hass: HomeAssistant, config: dict):

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):

    hass.data.setdefault(DOMAIN, {})

    client = MotionHttpClient(
        config_entry.data[CONF_HOST], config_entry.data[CONF_PORT],
        username=config_entry.data.get(CONF_USERNAME), password=config_entry.data.get(CONF_PASSWORD),
        tlsmode=MAP_TLS_MODE[config_entry.data.get(CONF_TLS_MODE, CONF_OPTION_AUTO)],
        session=async_get_clientsession(hass),
        logger=LOGGER
        )
    try:
        await client.update(updatecameras=True)
    except MotionHttpClientError as err:
        await client.close()
        raise ConfigEntryNotReady from err

    if not client.is_available:
        raise ConfigEntryNotReady

    api = MotionFrontendApi()
    api.client = client
    api.unsub_entry_update_listener = config_entry.add_update_listener(api.entry_update_listener)

    webhook_mode = config_entry.data.get(CONF_WEBHOOK_MODE)
    if webhook_mode != CONF_OPTION_NONE:
        # setup webhook to manage 'push' from motion server
        try:
            webhook_id = f"{DOMAIN}_{config_entry.entry_id}"
            hass.components.webhook.async_register(DOMAIN, DOMAIN, webhook_id, api.async_handle_webhook)
            api.webhook_id = webhook_id #set here after succesfully calling async_register
            webhook_address = config_entry.data.get(CONF_WEBHOOK_ADDRESS, CONF_OPTION_DEFAULT)
            if webhook_address == CONF_OPTION_INTERNAL:
                api.webhook_url = hass.helpers.network.get_url(
                    allow_internal=True,
                    allow_external=False,
                    allow_cloud=False)
            elif webhook_address == CONF_OPTION_EXTERNAL:
                api.webhook_url = hass.helpers.network.get_url(
                    allow_internal=False,
                    allow_external=True,
                    allow_cloud=True, prefer_cloud=False)
            elif webhook_address == CONF_OPTION_CLOUD:
                api.webhook_url = hass.helpers.network.get_url(
                    allow_internal=False,
                    allow_external=False,
                    allow_cloud=True, prefer_cloud=True)
            else:
                api.webhook_url = hass.helpers.network.get_url()
            api.webhook_url += hass.components.webhook.async_generate_path(api.webhook_id)

            force = (webhook_mode == CONF_OPTION_FORCE)

            config = client.config
            for event in MANAGED_EVENTS:
                hookcommand = "curl%20-d%20'" \
                                f"event={event};" \
                                "camera_id=%t;" \
                                "event_id=%v;" \
                                "filename=%f;" \
                                "filetype=%n" \
                                f"'%20{api.webhook_url}"

                command = config.get(event)
                if (command != hookcommand) and (force or (command is None)):
                    await client.config_set(event, hookcommand)

            LOGGER.info("Registered webhook for motion events")
        except Exception as exception:
            LOGGER.exception("exception (%s) setting up webhook", str(exception))
            if api.webhook_id:
                hass.components.webhook.async_unregister(api.webhook_id) # this is actually 'safe'
                api.webhook_id = None
                api.webhook_url = None

    hass.data[DOMAIN][config_entry.entry_id] = api

    # setup media_source entry to access server recordings if they're local
    if config_entry.data.get(CONF_MEDIASOURCE):
        try:
            media_dir_id = f"{DOMAIN}_{client.unique_id}"
            if media_dir_id not in hass.config.media_dirs:
                target_dir = client.target_dir
                if target_dir:
                    raise_if_invalid_path(target_dir)
                    if os.access(target_dir, os.R_OK):
                        hass.config.media_dirs[media_dir_id] = target_dir
                        LOGGER.info("Registered media_dirs[%s] for motion server target_dir", media_dir_id)
                        api.media_dir_id = media_dir_id
                    else:
                        LOGGER.error("Missing read access for target recordings directory")

        except Exception as err:
            LOGGER.exception("exception (%s) setting up media_source directory", str(err))


    for p in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, p)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, p)
                for p in PLATFORMS
            ]
        )
    )

    if unload_ok:
        api: MotionFrontendApi = hass.data[DOMAIN][config_entry.entry_id]
        await api.client.close()
        if api.webhook_id:
            hass.components.webhook.async_unregister(api.webhook_id)
            api.webhook_id = None
        if api.media_dir_id:
            try:# better be safe...
                hass.config.media_dirs.pop(api.media_dir_id, None)
            except:
                pass
        if api.unsub_entry_update_listener:
            api.unsub_entry_update_listener()
            api.unsub_entry_update_listener = None
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok



class MotionFrontendApi:
    client: MotionHttpClient = None
    webhook_id: str = None
    webhook_url: str = None
    media_dir_id: str = None
    unsub_entry_update_listener = None
    _cameras: list = []


    def register_cameras(self, cameras: list):
        self._cameras = cameras
        return


    def register_camera(self, camera):
        if camera not in self._cameras:
            self._cameras.append(camera)
        else:
            LOGGER.warning("register_camera: camera(%s) already registered", camera.unique_id)
        return

    def unregister_camera(self, camera):
        if camera in self._cameras:
            self._cameras.remove(camera)
        else:
            LOGGER.warning("unregister_camera: camera(%s) not registered", camera.unique_id)
        return

    async def async_handle_webhook(self, hass: HomeAssistant, webhook_id: str, request: aiohttp.web.Request):
        try:
            with async_timeout.timeout(5):
                data = dict(await request.post())

            LOGGER.debug("Received webhook - (%s)", data)

            camera_id = int(data.get("camera_id"))
            for camera in self._cameras:
                if camera.motioncamera.camera_id == camera_id:
                    if self.media_dir_id:
                        try:# fix the path as a media_source compatible url
                            filename = data.get(EXTRA_ATTR_FILENAME)
                            if filename:
                                filename = Path(filename).relative_to(self.client.target_dir)
                                data[EXTRA_ATTR_FILENAME] = f"{self.media_dir_id}/{str(filename)}"
                        except:
                            pass
                    camera.handle_event(data)
                    break

        except (asyncio.TimeoutError, aiohttp.web.HTTPException) as error:
            LOGGER.error("async_handle_webhook - exception (%s)", error)

        return


    @callback
    async def entry_update_listener(self, hass: HomeAssistant, config_entry: ConfigEntry):
        await hass.config_entries.async_reload(config_entry.entry_id)
        return

