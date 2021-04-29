from typing import Any, Mapping
from datetime import timedelta

from homeassistant.components.camera import (
    STATE_IDLE, STATE_RECORDING, STATE_STREAMING
)
from homeassistant.components.mjpeg.camera import (
    MjpegCamera,
    CONF_MJPEG_URL,CONF_STILL_IMAGE_URL, CONF_VERIFY_SSL,
    CONF_AUTHENTICATION, CONF_USERNAME, CONF_PASSWORD,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION,
    filter_urllib3_logging,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers import entity_platform
from homeassistant.helpers.typing import StateType

from .motionclient import (
    TlsMode,
    MotionHttpClient, MotionHttpClientError,
    MotionCamera
)
from .helpers import LOGGER
from .const import (
    #ATTRIBUTION,
    #CAMERA_SCAN_INTERVAL_SECS,
    DOMAIN,
    STATE_MOTION,
    EXTRA_ATTR_EVENT_ID, EXTRA_ATTR_FILENAME,
    ON_CAMERA_FOUND, ON_CAMERA_LOST,
    ON_EVENT_START, ON_EVENT_END,
    ON_AREA_DETECTED, ON_MOTION_DETECTED,
    ON_MOVIE_START, ON_MOVIE_END, ON_PICTURE_SAVE
)

#SCAN_INTERVAL = timedelta(seconds=CAMERA_SCAN_INTERVAL_SECS)

"""
_DEV_EN_ALT = "enable_alerts"
_DEV_DS_ALT = "disable_alerts"
_DEV_EN_REC = "start_recording"
_DEV_DS_REC = "stop_recording"
_DEV_SNAP = "snapshot"

CAMERA_SERVICES = {
    _DEV_EN_ALT: "async_enable_alerts",
    _DEV_DS_ALT: "async_disable_alerts",
    _DEV_EN_REC: "async_start_recording",
    _DEV_DS_REC: "async_stop_recording",
    _DEV_SNAP: "async_snapshot",
}
"""

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Agent cameras."""
    filter_urllib3_logging()

    api = hass.data[DOMAIN][config_entry.entry_id]
    client: MotionHttpClient = api.client

    cameras = []
    for camera in client.cameras.values():
        cameras.append(Camera(camera, config_entry.entry_id))

    async_add_entities(cameras)

    api.register_cameras(cameras)

    """
    #platform = entity_platform.current_platform.get()
    #for service, method in CAMERA_SERVICES.items():
    #    platform.async_register_entity_service(service, {}, method)
    """

class Camera(MjpegCamera):

    def __init__(self, motioncamera: MotionCamera, entry_id):
        self._motioncamera = motioncamera
        self._entry_id = entry_id
        self._unique_id = f"motion_{motioncamera.config_url}"
        self._state = STATE_IDLE if motioncamera.connected else None
        self._extra_attr = {}

        device_info = {
            CONF_NAME: motioncamera.name,
            CONF_MJPEG_URL: motioncamera.stream_url,
            CONF_STILL_IMAGE_URL: motioncamera.image_url,
            CONF_VERIFY_SSL: motioncamera.client.tlsmode == TlsMode.STRICT
        }
        stream_auth_method = motioncamera.config.get("stream_auth_method")
        if stream_auth_method == 1:
            device_info[CONF_AUTHENTICATION] = HTTP_BASIC_AUTHENTICATION
            device_info[CONF_USERNAME] = motioncamera.name.lower()
            device_info[CONF_PASSWORD] = "password"
        elif stream_auth_method == 2:
            device_info[CONF_AUTHENTICATION] = HTTP_DIGEST_AUTHENTICATION
            device_info[CONF_USERNAME] = motioncamera.name.lower()
            device_info[CONF_PASSWORD] = "password"

        super().__init__(device_info)


    @property
    def motioncamera(self) -> MotionCamera:
        return self._motioncamera


    @property
    def unique_id(self) -> str:
        return self._unique_id


    @property
    def device_info(self):
        client = self._motioncamera.client
        return {
            "identifiers": {(DOMAIN, client.unique_id)},
            "name": client.server_url,
            "manufacturer": "motion-project.github.io",
            "sw_version": client.version,
        }


    @property
    def supported_features(self) -> int:
        #return SUPPORT_ON_OFF
        return 0


    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return False


    @property
    def should_poll(self) -> bool:
        return False


    @property
    def icon(self):
        return "mdi:camcorder"


    @property
    def available(self) -> bool:
        return self._state is not None


    @property
    def state(self) -> StateType:
        return self._state


    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return self._extra_attr


    """
    @property
    def is_recording(self) -> bool:
        return False

    @property
    def is_alerted(self) -> bool:
        return False

    @property
    def is_detected(self) -> bool:
        return False


    @property
    def is_on(self) -> bool:
        return True
    """


    @property
    def motion_detection_enabled(self):
        return True

    """
    async def async_update(self):
        try:
            await self.device.update()
            if self._removed:
                _LOGGER.debug("%s reacquired", self._name)
            self._removed = False
        except AgentError:
            # server still available - camera error
            if self.device.client.is_available and not self._removed:
                _LOGGER.error("%s lost", self._name)
                self._removed = True
    """
    """
    @property
    def extra_state_attributes(self):
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "editable": False,
            "enabled": self.is_on,
            "connected": self.connected,
            "detected": self.is_detected,
            "alerted": self.is_alerted,
            "has_ptz": self.device.has_ptz,
            "alerts_enabled": self.device.alerts_active,
        }
    """


    """
    async def async_enable_alerts(self):
        await self.device.alerts_on()

    async def async_disable_alerts(self):
        await self.device.alerts_off()

    async def async_enable_motion_detection(self):
        await self.device.detector_on()

    async def async_disable_motion_detection(self):
        await self.device.detector_off()

    async def async_start_recording(self):
        await self.device.record()

    async def async_stop_recording(self):
        await self.device.record_stop()

    async def async_turn_on(self):
        await self.device.enable()

    async def async_snapshot(self):
        await self.device.snapshot()

    async def async_turn_off(self):
        await self.device.disable()
        """

    async def async_added_to_hass(self) -> None:
        #api = self.hass.data[DOMAIN][self._entry_id]
        #api.register_camera(self)
        return


    async def async_will_remove_from_hass(self) -> None:
        #api = self.hass.data[DOMAIN][self._entry_id]
        #api.unregister_camera(self)
        return


    def handle_event(self, data: dict) -> None:
        event_id = data.get(EXTRA_ATTR_EVENT_ID)
        if event_id:
            self._extra_attr[EXTRA_ATTR_EVENT_ID] = event_id
        else:
            self._extra_attr.pop(EXTRA_ATTR_EVENT_ID, None)
        filename = data.get(EXTRA_ATTR_FILENAME)
        if filename:
            self._extra_attr[EXTRA_ATTR_FILENAME] = filename
        else:
            self._extra_attr.pop(EXTRA_ATTR_FILENAME, None)

        event = data.get("event")
        if event == ON_MOVIE_START:
            self._set_state(STATE_RECORDING)
        elif event == ON_MOVIE_END:
            self._set_state(STATE_IDLE)
        elif event == ON_EVENT_END:
            if self._state is not STATE_RECORDING:
                self._set_state(STATE_IDLE)
        elif event in (ON_MOTION_DETECTED, ON_EVENT_START, ON_AREA_DETECTED):
            if self._state is not STATE_RECORDING:
                self._set_state(STATE_MOTION)
        elif event == ON_CAMERA_FOUND:
            if self._state is not STATE_RECORDING:
                self._set_state(STATE_IDLE)
        elif event == ON_CAMERA_LOST:
            self._set_state(None)
        return

    def _set_state(self, state: str) -> None:
        if self._state != state:
            self._state = state
            if self.hass and self.enabled:
                self.async_write_ha_state()
        return
