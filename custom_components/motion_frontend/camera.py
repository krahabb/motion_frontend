from __future__ import annotations

import asyncio
from contextlib import closing
from functools import partial
from typing import Any, Mapping
import typing

import aiohttp

from homeassistant.components import camera
from homeassistant import const as hac
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

# from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
from homeassistant.helpers.typing import StateType
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from .const import (
    DOMAIN,
    EXTRA_ATTR_CONNECTED,
    EXTRA_ATTR_EVENT_ID,
    EXTRA_ATTR_FILENAME,
    EXTRA_ATTR_PAUSED,
    EXTRA_ATTR_TRIGGERED,
    ON_AREA_DETECTED,
    ON_CAMERA_FOUND,
    ON_CAMERA_LOST,
    ON_EVENT_END,
    ON_EVENT_START,
    ON_MOTION_DETECTED,
    ON_MOVIE_END,
    ON_MOVIE_START,
    ON_PICTURE_SAVE,
)
from .helpers import LOGGER
from .motionclient import (
    MotionCamera,
    TlsMode,
    config_schema as cs,
)

if typing.TYPE_CHECKING:
    from . import MotionFrontendApi

SERVICE_KEY_PARAM = "param"
SERVICE_KEY_VALUE = "value"
CAMERA_SERVICES = (
    (
        "config_set",
        vol.Schema({
            vol.Required(SERVICE_KEY_PARAM): str,
            vol.Required(SERVICE_KEY_VALUE): str,
        }),
        "async_config_set",
    ),
    ("makemovie", vol.Schema({}), "async_makemovie"),
    ("snapshot", vol.Schema({}), "async_snapshot"),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    api = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(api.cameras.values())

    if platform := entity_platform.current_platform.get():
        for service, schema, method in CAMERA_SERVICES:
            platform.async_register_entity_service(service, schema, method)


async def async_unload_entry(hass: HomeAssistant, config_entry):
    if len(hass.data[DOMAIN]) == 1:  # last config_entry for DOMAIN
        for service_entry in CAMERA_SERVICES:
            hass.services.async_remove(DOMAIN, service_entry[0])


def _extract_image_from_mjpeg(stream):
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b""
    for chunk in stream:
        data += chunk
        jpg_end = data.find(b"\xff\xd9")
        if jpg_end != -1:
            jpg_start = data.find(b"\xff\xd8")
            if jpg_start != -1:
                return data[jpg_start : jpg_end + 2]


class MotionFrontendCamera(camera.Camera, MotionCamera):
    client: MotionFrontendApi


    def __init__(self, client: MotionFrontendApi, id: str):
        MotionCamera.__init__(self, client, id)
        self._unique_id = f"{client.unique_id}_{self.camera_id}"
        self._recording = False
        self._triggered = False
        self._state = (
            hac.STATE_PROBLEM
            if not self.connected
            else hac.STATE_PAUSED
            if self.paused
            else camera.STATE_IDLE
        )
        self._attr_extra_state_attributes = {}
        self._camera_image = None  # cached copy
        self._available = True
        camera.Camera.__init__(self)

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self):
        return self.client.device_info

    @property
    def assumed_state(self) -> bool:
        return False

    @property
    def should_poll(self):
        return False

    @property
    def icon(self):
        return "mdi:camcorder"

    @property
    def name(self):
        return self.config.get(cs.CAMERA_NAME, self.camera_id)

    @property
    def available(self):
        return self.client.is_available and self._available

    @property
    def state(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return self._attr_extra_state_attributes

    @property
    def is_recording(self):
        return self._recording

    @property
    def motion_detection_enabled(self):
        return not self.paused

    # override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self.connected:
            # only pull the stream/image when the remote is connected
            # so we both save bandwith and we're able to deliver an
            # old snapshot when camera get out of reach
            try:
                # DigestAuth is not supported by aiohttp
                image_url = self.image_url
                stream_auth_method = self.config.get(cs.STREAM_AUTH_METHOD)
                if (image_url is None) or (stream_auth_method == cs.AUTH_MODE_DIGEST):
                    self._camera_image = await self.hass.async_add_executor_job(
                        partial(self.camera_image, width=width, height=height)
                    )
                    if not self._available:
                        self._updatestate()
                    return self._camera_image

                websession = async_get_clientsession(
                    self.hass, verify_ssl=(self.client.tlsmode == TlsMode.STRICT)
                )
                if stream_auth_method == cs.AUTH_MODE_BASIC:
                    stream_authentication = self.stream_authentication
                    auth = aiohttp.BasicAuth(
                        stream_authentication[0], stream_authentication[-1]
                    )
                else:
                    auth = None

                async with asyncio.timeout(10):
                    response = await websession.get(image_url, auth=auth)
                    self._camera_image = await response.read()
                    if not self._available:
                        self._updatestate()
                    return self._camera_image

            except Exception as exception:
                LOGGER.warning(
                    "Error (%s) fetching image from %s", str(exception), self.name
                )
                self._set_state(None)

        return self._camera_image

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """
        Return a still image response from the camera.
        This is called whenever auth is like DIGEST or
        we don't have a real jpeg endpoint and we need
        to parse the MJPEG stream
        """
        stream_auth_method = self.config.get(cs.STREAM_AUTH_METHOD)
        auth = None
        if stream_auth_method:
            stream_authentication = self.stream_authentication
            if stream_auth_method == cs.AUTH_MODE_BASIC:
                auth = HTTPBasicAuth(
                    stream_authentication[0], stream_authentication[-1]
                )
            elif stream_auth_method == cs.AUTH_MODE_DIGEST:
                auth = HTTPDigestAuth(
                    stream_authentication[0], stream_authentication[-1]
                )

        req = requests.get(
            self.stream_url,
            auth=auth,
            stream=True,
            timeout=10,
            verify=(self.client.tlsmode == TlsMode.STRICT),
        )

        with closing(req) as response:
            return _extract_image_from_mjpeg(response.iter_content(102400))

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        # aiohttp don't support DigestAuth -> Fallback
        stream_auth_method = self.config.get(cs.STREAM_AUTH_METHOD)
        auth = None
        if stream_auth_method == cs.AUTH_MODE_DIGEST:
            return await super().handle_async_mjpeg_stream(request)
        elif stream_auth_method == cs.AUTH_MODE_BASIC:
            stream_authentication = self.stream_authentication
            auth = aiohttp.BasicAuth(
                stream_authentication[0], stream_authentication[-1]
            )

        # connect to stream
        websession = async_get_clientsession(
            self.hass, verify_ssl=(self.client.tlsmode == TlsMode.STRICT)
        )
        stream_coro = websession.get(self.stream_url, auth=auth)
        return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

    """
    services
    """
    """
    async def async_config_set(self, param: str, value: str, persist: bool) -> None:
        handled in base MotionClient
    """

    # inherited from camera platform service call
    async def async_enable_motion_detection(self):
        await self.client.async_detection_start(self._id)

    # inherited from camera platform service call
    async def async_disable_motion_detection(self):
        await self.client.async_detection_pause(self._id)

    def handle_event(self, data: dict) -> None:
        event_id = data.get(EXTRA_ATTR_EVENT_ID)
        if event_id:
            self._attr_extra_state_attributes[EXTRA_ATTR_EVENT_ID] = event_id
        filename = data.get(EXTRA_ATTR_FILENAME)
        if filename:
            self._attr_extra_state_attributes[EXTRA_ATTR_FILENAME] = filename

        event = data.get("event")
        if event == ON_MOVIE_START:
            self._setrecording(True)
        elif event == ON_MOVIE_END:
            self._setrecording(False)
        elif event == ON_EVENT_END:
            self._settriggered(False)
        elif event in (ON_MOTION_DETECTED, ON_EVENT_START, ON_AREA_DETECTED):
            self._settriggered(True)
        elif event == ON_CAMERA_FOUND:
            self._setconnected(True)
        elif event == ON_CAMERA_LOST:
            self._setconnected(False)
        return

    def _setrecording(self, recording: bool):
        if self._recording != recording:
            self._recording = recording
            self._updatestate()

    @property
    def is_triggered(self):
        return self._triggered

    def _settriggered(self, triggered: bool):
        if self._triggered != triggered:
            self._triggered = triggered
            self._attr_extra_state_attributes[EXTRA_ATTR_TRIGGERED] = triggered
            self._updatestate()

    # override MotionCamera
    def on_connected_changed(self):
        self._attr_extra_state_attributes[EXTRA_ATTR_CONNECTED] = self.connected
        self._updatestate()

    # override MotionCamera
    def on_paused_changed(self):
        self._attr_extra_state_attributes[EXTRA_ATTR_PAUSED] = self.paused
        self._updatestate()

    def _updatestate(self):
        """
        called every time an underlying state related property changes
        this will not always trigger an HA state change (see _set_state)
        """
        if self.connected:
            if self._recording:
                self._set_state(camera.STATE_RECORDING)
            elif self._triggered:
                self._set_state(hac.STATE_ALARM_TRIGGERED)
            elif self.paused:
                self._set_state(hac.STATE_PAUSED)
            else:
                self._set_state(camera.STATE_IDLE)
        else:
            self._set_state(hac.STATE_PROBLEM)
        # we'll notify our api here since HA state could have not changed
        # but some inner property has
        self.client.notify_state_changed(self)

    def _set_state(self, state: str | None) -> None:
        # we'll get here since an underlying state changed
        # we always save to HA since even tho _state has not changed
        # something might have in attributes
        self._state = state
        self._available = state is not None
        if self.hass and self.enabled:
            self.async_write_ha_state()
