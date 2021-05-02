"""Support for Motion daemon DVR Alarm Control Panels."""
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    FORMAT_TEXT, FORMAT_NUMBER
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_HOME, SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS
)
from homeassistant.const import (
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_TRIGGERED,
)

from .motionclient import (
    MotionHttpClient,
)
from .helpers import LOGGER
from .const import (
    DOMAIN,
)


async def async_setup_entry(hass, config_entry, async_add_entities):

    async_add_entities(
        [MotionFrontendAlarmControlPanel(hass.data[DOMAIN][config_entry.entry_id])]
    )


class MotionFrontendAlarmControlPanel(AlarmControlPanelEntity):

    def __init__(self, client: MotionHttpClient):
        self._client = client
        self._unique_id = f"{client.unique_id}_CP"
        self._name = f"{client.name} Alarm Panel"
        self._state = None # TODO: persist and restore armed/unarmed state into motion config
        self._armmode = None


    @property
    def unique_id(self) -> str:
        return self._unique_id


    @property
    def device_info(self):
        return self._client.device_info


    @property
    def icon(self):
        return "mdi:security"


    @property
    def state(self):
        return self._state


    @property
    def supported_features(self) -> int:
        return SUPPORT_ALARM_ARM_HOME|SUPPORT_ALARM_ARM_AWAY|SUPPORT_ALARM_ARM_CUSTOM_BYPASS


    @property
    def code_format(self):
        return None


    @property
    def name(self):
        return self._name


    @property
    def available(self) -> bool:
        return self._client.is_available


    async def async_update(self):
        await self._client.async_detection_status()
        # right now we'll considered armed if any of the cameras
        # is actively detecting
        disarmed = True
        triggered = False
        cantrigger = self._armmode not in (STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_CUSTOM_BYPASS)
        for camera in self._client.cameras.values():
            disarmed &= camera.paused
            triggered |= cantrigger and camera.is_triggered

        self._state = STATE_ALARM_DISARMED if disarmed \
            else STATE_ALARM_TRIGGERED if triggered \
            else self._armmode


    async def async_alarm_disarm(self, code=None):
        await self._client.async_detection_pause()
        self._armmode = self._state = STATE_ALARM_DISARMED


    async def async_alarm_arm_home(self, code=None):
        await self._client.async_detection_start()
        self._armmode = self._state = STATE_ALARM_ARMED_HOME


    async def async_alarm_arm_away(self, code=None):
        await self._client.async_detection_start()
        self._armmode = self._state = STATE_ALARM_ARMED_AWAY


    async def async_alarm_arm_custom_bypass(self, code=None):
        await self._client.async_detection_start()
        self._armmode = self._state = STATE_ALARM_ARMED_CUSTOM_BYPASS
