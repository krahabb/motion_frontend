"""Support for Motion daemon DVR Alarm Control Panels."""

from __future__ import annotations

import typing

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_PIN

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

if typing.TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from . import MotionFrontendApi


async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities(
        [MotionFrontendAlarmControlPanel(hass.data[DOMAIN][config_entry.entry_id])]
    )


class MotionFrontendAlarmControlPanel(AlarmControlPanelEntity):

    _attr_should_poll = True
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    alarm_state: AlarmControlPanelState
    code_arm_required: bool
    code_format: CodeFormat | None
    device_info: "DeviceInfo"
    extra_state_attributes: dict
    name: str
    unique_id: str

    _armmode: AlarmControlPanelState
    _disarm_sets: dict[AlarmControlPanelState, frozenset]
    _current_disarm_set: frozenset

    DISARM_SET_MAP = {
        AlarmControlPanelState.ARMED_HOME: CONF_ALARM_DISARMHOME_CAMERAS,
        AlarmControlPanelState.ARMED_AWAY: CONF_ALARM_DISARMAWAY_CAMERAS,
        AlarmControlPanelState.ARMED_NIGHT: CONF_ALARM_DISARMNIGHT_CAMERAS,
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS: CONF_ALARM_DISARMBYPASS_CAMERAS,
    }

    __slots__ = (
        "alarm_state",
        "code_arm_required",
        "code_format",
        "device_info",
        "extra_state_attributes",
        "name",
        "unique_id",
        "_api",
        "_armmode",
        "_pin",
        "_pause_disarmed",
        "_disarm_sets",
        "_current_disarm_set",
    )

    def __init__(self, api: MotionFrontendApi):
        self._api = api
        self._armmode = AlarmControlPanelState.DISARMED
        data = api.config_data.get(CONF_OPTION_ALARM, {})
        self._pin: str = str(data.get(CONF_PIN))
        self._pause_disarmed: bool = data.get(CONF_ALARM_PAUSE_DISARMED, False)
        self._disarm_sets = {}
        self._current_disarm_set = frozenset()
        for _state, _config_key in self.DISARM_SET_MAP.items():
            self._disarm_sets[_state] = frozenset(data.get(_config_key, []))

        self.alarm_state = AlarmControlPanelState.DISARMED
        self.code_arm_required = bool(self._pin)
        self.code_format = (
            (CodeFormat.NUMBER if self._pin.isnumeric() else CodeFormat.TEXT)
            if self._pin
            else None
        )
        self.device_info = self._api.device_info
        self.extra_state_attributes = {}
        self.name = f"{api.name} Alarm Panel"
        self.unique_id = f"{api.unique_id}_CP"

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
            for _state, _disarm_set in self._disarm_sets.items():
                if disarmed == _disarm_set:
                    self._current_disarm_set = _disarm_set
                    self.alarm_state = self._armmode = _state
                    break

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
        if not self._api.is_available:
            self._set_state(AlarmControlPanelState.PENDING)

    async def async_added_to_hass(self) -> None:
        self._api.alarm_control_panel = self

    async def async_will_remove_from_hass(self) -> None:
        self._api.alarm_control_panel = None

    async def async_alarm_disarm(self, code=None):
        if code == self._pin:
            self._current_disarm_set = frozenset()
            if self._pause_disarmed:
                for camera in self._api.cameras.values():
                    camera.paused = True
            self._set_armmode(AlarmControlPanelState.DISARMED)

    async def async_alarm_arm_home(self, code=None):
        if code == self._pin:
            await self._async_alarm_arm_state(AlarmControlPanelState.ARMED_HOME)

    async def async_alarm_arm_away(self, code=None):
        if code == self._pin:
            await self._async_alarm_arm_state(AlarmControlPanelState.ARMED_AWAY)

    async def async_alarm_arm_night(self, code=None):
        if code == self._pin:
            await self._async_alarm_arm_state(AlarmControlPanelState.ARMED_NIGHT)

    async def async_alarm_arm_custom_bypass(self, code=None):
        if code == self._pin:
            await self._async_alarm_arm_state(
                AlarmControlPanelState.ARMED_CUSTOM_BYPASS
            )

    async def _async_alarm_arm_state(self, state: AlarmControlPanelState):
        self._current_disarm_set = self._disarm_sets[state]
        if self._pause_disarmed:
            for camera in self._api.cameras.values():
                camera.paused = camera.id in self._current_disarm_set
        self._set_armmode(state)

    def notify_state_changed(self, camera: MotionFrontendCamera):
        if self._armmode is AlarmControlPanelState.DISARMED:
            return

        if camera.id in self._current_disarm_set:
            return

        if camera.is_triggered:
            self.extra_state_attributes[EXTRA_ATTR_LAST_TRIGGERED] = camera.entity_id
            self._set_state(AlarmControlPanelState.TRIGGERED)
            return

        if not camera.connected:
            self.extra_state_attributes[EXTRA_ATTR_LAST_PROBLEM] = camera.entity_id
            if self.alarm_state is not AlarmControlPanelState.TRIGGERED:
                # We'll use PENDING to indicate a camera connection problem
                self._set_state(AlarmControlPanelState.PENDING)
                return

        # if not any 'rising' event then check the state of all the other
        problem = False
        for _id, _camera in self._api.cameras.items():
            if _id in self._current_disarm_set:
                continue
            if _camera.is_triggered:
                self._set_state(AlarmControlPanelState.TRIGGERED)
                break
            problem |= not _camera.connected
        else:
            # We'll use PENDING to indicate a camera connection problem
            self._set_state(
                AlarmControlPanelState.PENDING if problem else self._armmode
            )

    def _set_armmode(self, state: AlarmControlPanelState) -> None:
        if self._armmode != state:
            self._armmode = state
            self._set_state(state)

    def _set_state(self, state: AlarmControlPanelState) -> None:
        if self.alarm_state != state:
            self.alarm_state = state
            if self.hass and self.enabled:
                self.async_write_ha_state()
