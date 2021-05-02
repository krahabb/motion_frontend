from typing import Any, Mapping
import voluptuous as vol
from datetime import timedelta

from homeassistant.components.camera import (
    SUPPORT_STREAM,
    STATE_IDLE, STATE_RECORDING, STATE_STREAMING
)
from homeassistant.components.mjpeg.camera import (
    MjpegCamera,
    CONF_MJPEG_URL,CONF_STILL_IMAGE_URL, CONF_VERIFY_SSL,
    CONF_AUTHENTICATION, CONF_USERNAME, CONF_PASSWORD,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION,
    filter_urllib3_logging,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME,
    STATE_PAUSED, STATE_PROBLEM, STATE_ALARM_TRIGGERED
)
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
    #STATE_MOTION,
    EXTRA_ATTR_EVENT_ID, EXTRA_ATTR_FILENAME,
    ON_CAMERA_FOUND, ON_CAMERA_LOST,
    ON_EVENT_START, ON_EVENT_END,
    ON_AREA_DETECTED, ON_MOTION_DETECTED,
    ON_MOVIE_START, ON_MOVIE_END, ON_PICTURE_SAVE
)

#SCAN_INTERVAL = timedelta(seconds=CAMERA_SCAN_INTERVAL_SECS)


#_DEV_EN_ALT = "enable_alerts"
#_DEV_DS_ALT = "disable_alerts"
#_DEV_EN_REC = "start_recording"
#_DEV_DS_REC = "stop_recording"
#_DEV_SNAP = "snapshot"
    #_DEV_EN_ALT: "async_enable_alerts",
    #_DEV_DS_ALT: "async_disable_alerts",
    #_DEV_EN_REC: "async_start_recording",
    #_DEV_DS_REC: "async_stop_recording",
    #_DEV_SNAP: "async_snapshot",

SERVICE_KEY_PARAM = "param"
SERVICE_KEY_VALUE = "value"
SERVICE_CONFIG_SET = "config_set"
CAMERA_SERVICES = (
    ("config_set", {
        vol.Required(SERVICE_KEY_PARAM): str,
        vol.Required(SERVICE_KEY_VALUE): str
    },
    "async_config_set"
    ),
    ("makemovie", {
    },
    "async_makemovie"
    ),
    ("snapshot", {
    },
    "async_snapshot"
    ),
)



async def async_setup_entry(hass, config_entry, async_add_entities):

    filter_urllib3_logging() # agent_dvr integration does this...

    api = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(api.cameras.values())

    platform = entity_platform.current_platform.get()
    for service, schema, method in CAMERA_SERVICES:
        platform.async_register_entity_service(service, schema, method)


class MotionFrontendCamera(MjpegCamera, MotionCamera):

    def __init__(self, client: MotionHttpClient, id: int):
        MotionCamera.__init__(self, client, id)
        self._unique_id = f"{client.unique_id}_{self.camera_id}"
        self._recording = False
        self._triggered = False
        self._state = STATE_PROBLEM if not self.connected else STATE_PAUSED if self.paused else STATE_IDLE
        self._extra_attr = {}
        self._camera_image = None # cached copy
        self._available = True

        device_info = {
            CONF_MJPEG_URL: self.stream_url,
            CONF_STILL_IMAGE_URL: self.image_url,
            CONF_VERIFY_SSL: client.tlsmode == TlsMode.STRICT
        }
        try:
            stream_auth_method = self.config.get("stream_auth_method")
            if stream_auth_method:
                stream_authentication = self.config.get("stream_authentication", "username:password")
                stream_authentication = stream_authentication.split(":")
                device_info[CONF_USERNAME] = stream_authentication[0]
                device_info[CONF_PASSWORD] = stream_authentication[-1]
                device_info[CONF_AUTHENTICATION] = HTTP_DIGEST_AUTHENTICATION if stream_auth_method == 2 else HTTP_BASIC_AUTHENTICATION
        except Exception as exception:
            LOGGER.warning("Error (%s) setting up camera authentication", str(exception))

        MjpegCamera.__init__(self, device_info)


    @property
    def unique_id(self) -> str:
        return self._unique_id


    @property
    def device_info(self):
        return self.client.device_info


    @property
    def supported_features(self) -> int:
        return SUPPORT_STREAM


    @property
    def assumed_state(self) -> bool:
        return False


    @property
    def should_poll(self) -> bool:
        return False


    @property
    def icon(self):
        return "mdi:camcorder"


    @property
    def name(self) -> str:
        return self.config.get("camera_name", self.camera_id)


    @property
    def available(self) -> bool:
        return self.client.is_available and self._available


    @property
    def state(self) -> StateType:
        return self._state


    @property
    def is_recording(self):
        return self._recording


    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return self._extra_attr


    @property
    def motion_detection_enabled(self):
        return not self.paused


    async def async_added_to_hass(self) -> None:
        return


    async def async_will_remove_from_hass(self) -> None:
        return


    # override
    async def async_camera_image(self):
        if self.connected:
            # only pull the stream/image when the remote is connected
            # so we both save bandwith and we're able to deliver an
            # old snapshot when camera get out of reach
            if image := await super().async_camera_image():
                self._camera_image = image
                self._available = True
            else:
                self._available = False
        return self._camera_image

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
            self._extra_attr[EXTRA_ATTR_EVENT_ID] = event_id
        filename = data.get(EXTRA_ATTR_FILENAME)
        if filename:
            self._extra_attr[EXTRA_ATTR_FILENAME] = filename

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
            self._updatestate()


    #override MotionCamera
    def on_connected_changed(self):
        self._updatestate()


    #override MotionCamera
    def on_paused_changed(self):
        self._updatestate()


    def _updatestate(self):
        if self.connected:
            if self._recording:
                self._set_state(STATE_RECORDING)
            elif self._triggered:
                self._set_state(STATE_ALARM_TRIGGERED)
            elif self.paused:
                self._set_state(STATE_PAUSED)
            else:
                self._set_state(STATE_IDLE)
        else:
            self._set_state(STATE_PROBLEM)


    def _set_state(self, state: str) -> None:
        if self._state != state:
            self._state = state
            if self.hass and self.enabled:
                self.async_write_ha_state()
