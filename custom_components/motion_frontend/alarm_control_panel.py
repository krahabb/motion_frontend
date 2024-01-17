"""Support for Motion daemon DVR Alarm Control Panels."""
from __future__ import annotations

import typing

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.const import (
    CONF_PIN,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_PAUSED,
    STATE_PROBLEM,
)

from .camera import MotionFrontendCamera
from .const import (
    CONF_ALARM_DISARMAWAY_CAMERAS,
    CONF_ALARM_DISARMBYPASS_CAMERAS,
    CONF_ALARM_DISARMHOME_CAMERAS,
    CONF_ALARM_DISARMNIGHT_CAMERAS,
    CONF_ALARM_PAUSE_DISARMED,
    CONF_OPTION_ALARM,
    DOMAIN,
    EXTRA_ATTR_LAST_PROBLEM,
    EXTRA_ATTR_LAST_TRIGGERED,
)
from .helpers import LOGGER

if typing.TYPE_CHECKING:
    from . import MotionFrontendApi


async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities(
        [MotionFrontendAlarmControlPanel(hass.data[DOMAIN][config_entry.entry_id])]
    )


class MotionFrontendAlarmControlPanel(AlarmControlPanelEntity):
    def __init__(self, api: MotionFrontendApi):
        self._api = api
        self._unique_id = f"{api.unique_id}_CP"
        self._name = f"{api.name} Alarm Panel"
        self._state = STATE_ALARM_DISARMED
        self._attr_extra_state_attributes = {}
        self._armmode = STATE_ALARM_DISARMED
        data = api.config_data.get(CONF_OPTION_ALARM, {})
        self._pin: str = str(data.get(CONF_PIN))
        self._pause_disarmed: bool = data.get(CONF_ALARM_PAUSE_DISARMED, False)
        self._disarmhome_cameras: frozenset = frozenset(
            data.get(CONF_ALARM_DISARMHOME_CAMERAS, [])
        )
        self._disarmaway_cameras: frozenset = frozenset(
            data.get(CONF_ALARM_DISARMAWAY_CAMERAS, [])
        )
        self._disarmnight_cameras: frozenset = frozenset(
            data.get(CONF_ALARM_DISARMNIGHT_CAMERAS, [])
        )
        self._disarmbypass_cameras: frozenset = frozenset(
            data.get(CONF_ALARM_DISARMBYPASS_CAMERAS, [])
        )
        self._disarmed_cameras: frozenset = frozenset()
        """
        The following code is a bit faulty since it depends on cameras being correctly initialized
        and updated at the moment of this execution
        """
        # try to determine startup state by inspecting cameras setup
        if (
            self._pause_disarmed
        ):  # the set of disarmed cameras should match with some of our state-sets
            disarmed = {
                camera.id for camera in self._api.cameras.values() if camera.paused
            }
            # bear in mind only the first matching state/set gets assigned
            # if 2 or more disarm...cameras are the same there's no way to tell the difference
            if disarmed == self._disarmhome_cameras:
                self._disarmed_cameras = self._disarmhome_cameras
                self._state = self._armmode = STATE_ALARM_ARMED_HOME
            elif disarmed == self._disarmaway_cameras:
                self._disarmed_cameras = self._disarmaway_cameras
                self._state = self._armmode = STATE_ALARM_ARMED_AWAY
            elif disarmed == self._disarmnight_cameras:
                self._disarmed_cameras = self._disarmnight_cameras
                self._state = self._armmode = STATE_ALARM_ARMED_NIGHT
            elif disarmed == self._disarmbypass_cameras:
                self._disarmed_cameras = self._disarmbypass_cameras
                self._state = self._armmode = STATE_ALARM_ARMED_CUSTOM_BYPASS

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self):
        return self._api.device_info

    @property
    def icon(self):
        return "mdi:security"

    @property
    def assumed_state(self) -> bool:
        return False

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def supported_features(self) -> int:
        return (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
            | AlarmControlPanelEntityFeature.ARM_NIGHT
        )

    @property
    def code_format(self):
        if self._pin:
            return CodeFormat.NUMBER if self._pin.isnumeric() else CodeFormat.TEXT
        return None

    @property
    def code_arm_required(self):
        return self._pin is not None and len(self._pin) > 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return True

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attr_extra_state_attributes

    async def async_update(self):
        """
        this polling is not necessary overall
        since we're able to get notified from camera events and 'push'
        state updates for this entity but sometimes when the server disconnects
        we'll idle out not being able to receive any state change (not even the disconnection)
        """
        """
        if self.enabled:# in HA terms I guess we shouldnt get here if disabled (but better safe than sorry)
            await self._api.async_detection_status()
            if self._available != self._api.is_available:
                self._available = self._api.is_available
                self.async_write_ha_state()
        """
        await self._api.async_detection_status()
        if (not self._api.is_available) and (self._state != STATE_PROBLEM):
            self._set_state(STATE_PROBLEM)

    async def async_added_to_hass(self) -> None:
        self._api.alarm_control_panel = self

    async def async_will_remove_from_hass(self) -> None:
        self._api.alarm_control_panel = None

    async def async_alarm_disarm(self, code=None):
        if code == self._pin:
            if self._pause_disarmed:
                for camera in self._api.cameras.values():
                    camera.paused = True
            self._disarmed_cameras = frozenset()
            self._set_armmode(STATE_ALARM_DISARMED)

    async def async_alarm_arm_home(self, code=None):
        if code == self._pin:
            if self._pause_disarmed:
                for camera in self._api.cameras.values():
                    camera.paused = camera.id in self._disarmhome_cameras
            self._disarmed_cameras = self._disarmhome_cameras
            self._set_armmode(STATE_ALARM_ARMED_HOME)

    async def async_alarm_arm_away(self, code=None):
        if code == self._pin:
            if self._pause_disarmed:
                for camera in self._api.cameras.values():
                    camera.paused = camera.id in self._disarmaway_cameras
            self._disarmed_cameras = self._disarmaway_cameras
            self._set_armmode(STATE_ALARM_ARMED_AWAY)

    async def async_alarm_arm_night(self, code=None):
        if code == self._pin:
            if self._pause_disarmed:
                for camera in self._api.cameras.values():
                    camera.paused = camera.id in self._disarmnight_cameras
            self._disarmed_cameras = self._disarmnight_cameras
            self._set_armmode(STATE_ALARM_ARMED_NIGHT)

    async def async_alarm_arm_custom_bypass(self, code=None):
        if code == self._pin:
            if self._pause_disarmed:
                for camera in self._api.cameras.values():
                    camera.paused = camera.id in self._disarmbypass_cameras
            self._disarmed_cameras = self._disarmbypass_cameras
            self._set_armmode(STATE_ALARM_ARMED_CUSTOM_BYPASS)

    def notify_state_changed(self, camera: MotionFrontendCamera):
        if self._armmode is STATE_ALARM_DISARMED:
            return

        if camera.id in self._disarmed_cameras:
            return

        if camera.is_triggered:
            self._attr_extra_state_attributes[
                EXTRA_ATTR_LAST_TRIGGERED
            ] = camera.entity_id
            self._set_state(STATE_ALARM_TRIGGERED)
            return

        if camera.state == STATE_PROBLEM:
            self._attr_extra_state_attributes[
                EXTRA_ATTR_LAST_PROBLEM
            ] = camera.entity_id
            if self._state != STATE_ALARM_TRIGGERED:
                self._set_state(STATE_PROBLEM)  # report camera 'PROBLEM' to this alarm
                return

        # if not any 'rising' event then check the state of all the other
        problem = False
        for _id, _camera in self._api.cameras.items():
            if id in self._disarmed_cameras:
                continue
            if _camera.is_triggered:
                self._set_state(STATE_ALARM_TRIGGERED)
                break
            problem |= (_camera.state == STATE_PROBLEM)
        else:
            self._set_state(STATE_PROBLEM if problem else self._armmode)

    def _set_armmode(self, state: str) -> None:
        if self._armmode != state:
            self._armmode = state
            self._set_state(state)

    def _set_state(self, state: str) -> None:
        if self._state != state:
            self._state = state
            if self.hass and self.enabled:
                self.async_write_ha_state()
