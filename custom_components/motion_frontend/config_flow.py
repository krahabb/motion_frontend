"""Config flow to configure Agent devices."""
from __future__ import annotations

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_DELAY_TIME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_ALARM_DISARMAWAY_CAMERAS,
    CONF_ALARM_DISARMBYPASS_CAMERAS,
    CONF_ALARM_DISARMHOME_CAMERAS,
    CONF_ALARM_DISARMNIGHT_CAMERAS,
    CONF_ALARM_PAUSE_DISARMED,
    CONF_MEDIASOURCE,
    CONF_OPTION_ALARM,
    CONF_OPTION_CONNECTION,
    CONF_OPTION_NONE,
    CONF_OPTION_UNKNOWN,
    CONF_PORT_DEFAULT,
    CONF_TLS_MODE,
    CONF_TLS_MODE_OPTIONS,
    CONF_WEBHOOK_ADDRESS,
    CONF_WEBHOOK_ADDRESS_OPTIONS,
    CONF_WEBHOOK_MODE,
    CONF_WEBHOOK_MODE_OPTIONS,
    DOMAIN,
    MAP_TLS_MODE,
)
from .helpers import LOGGER
from .motionclient import (
    MotionHttpClient,
    MotionHttpClientConnectionError,
    MotionHttpClientError,
    config_schema as cs,
)

# OptionsFlow: async_step_init
CONF_SELECT_FLOW = "select_flow"
CONF_SELECT_FLOW_OPTIONS = {
    CONF_OPTION_NONE: CONF_OPTION_NONE,
    CONF_OPTION_CONNECTION: "Connection",
    CONF_OPTION_ALARM: "Alarm Panel",
    ### we'll add the keys (one each) at runtime for the camera config(s)
    ### so to be able to access any camera (or global) configuration
}

# OptionsFlow: async_step_config
CONF_SELECT_CONFIG = "select_config"
CONF_SELECT_CONFIG_OPTIONS = {
    CONF_OPTION_NONE: CONF_OPTION_NONE,
    cs.SECTION_SYSTEM: "System setup",
    cs.SECTION_STREAM: "Streaming",
    cs.SECTION_IMAGE: "Image processing",
    cs.SECTION_MOTION: "Motion detection",
    cs.SECTION_SCRIPT: "Script / events",
    cs.SECTION_PICTURE: "Picture",
    cs.SECTION_MOVIE: "Movie",
    cs.SECTION_TIMELAPSE: "Timelapse",
    cs.SECTION_NETCAM: "Network cameras",
    cs.SECTION_V4L2: "V4L2 cameras",
    cs.SECTION_MMALCAM: "Raspberry PI cameras",
    cs.SECTION_DATABASE: "Database",
    cs.SECTION_TRACK: "Tracking",
    CONF_OPTION_UNKNOWN: "Miscellaneous",  # add an entry to setup all of the config params we didn't normalize
}


def _map_motion_cs_validator(descriptor: cs.Descriptor):
    """
    We're defining schemas in motionclient library bu validators there
    are more exotic than HA allows to serialize: provide here a fallback
    for unsupported serializations
    """
    if descriptor is None:
        return str
    val = descriptor.validator
    if val is cs.validate_userpass:
        return str
    if isinstance(
        val, vol.Range
    ):  # HA frontend doesnt recognize range of int really well
        return int
    return val or str


# link ref to documentation (set of different tags among versions)
SECTION_CONFIG_REF_MAP = {
    cs.SECTION_SYSTEM: ("OptDetail_System_Processing", "Options_System_Processing"),
    cs.SECTION_V4L2: ("OptDetail_Video4Linux_Devices", "Options_Video4Linux_Devices"),
    cs.SECTION_NETCAM: ("OptDetail_Network_Cameras", "Options_Network_Cameras"),
    cs.SECTION_MMALCAM: ("OptDetail_Raspi_Cameras", "Options_Raspi_Cameras"),
    cs.SECTION_STREAM: ("OptDetail_Stream", "Options_Stream_Webcontrol"),
    cs.SECTION_IMAGE: ("OptDetail_Image_Processing", "Options_Image_Processing"),
    cs.SECTION_MOTION: ("OptDetail_Motion_Detection", "Options_Motion_Detection"),
    cs.SECTION_SCRIPT: ("OptDetail_Scripts", "Options_Scripts"),
    cs.SECTION_PICTURE: ("OptDetail_Pictures", "Options_Pictures"),
    cs.SECTION_MOVIE: ("OptDetail_Movies", "Options_Movies"),
    cs.SECTION_TIMELAPSE: ("OptDetail_Movies", "Options_Movies"),
    cs.SECTION_DATABASE: ("OptDetail_Database", "Options_Database"),
    cs.SECTION_TRACK: ("OptDetail_Tracking", "Options_Tracking"),
}


def _get_config_section_url(version: str, section: str) -> str:
    if not version:
        version = "3.4.1"  # last known older ver
    if version.startswith("4.2"):
        page = "motion_config.html"
        refver = 0
    else:
        page = "motion_guide.html"
        refver = 1
    href = SECTION_CONFIG_REF_MAP.get(section)
    href = href[refver] if href else "Configuration_OptionsTopic"
    return f"https://motion-project.github.io/{version}/{page}#{href}"


class MotionFlowHandler(ConfigFlow, domain=DOMAIN):
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH
    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        client: MotionHttpClient | None = None

        if user_input is not None:
            client = MotionHttpClient(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
                tlsmode=MAP_TLS_MODE[
                    user_input.get(CONF_TLS_MODE, CONF_TLS_MODE_OPTIONS[0])
                ],
                session=async_get_clientsession(self.hass),
                logger=LOGGER,
            )

            try:
                await client.update()
            except MotionHttpClientError as err:
                if err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

            await client.close()

            if client.is_available:
                await self.async_set_unique_id(client.unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=client.unique_id, data=user_input)

        schema = {
            vol.Required(
                CONF_HOST,
                default="localhost",  # type: ignore
                description={"suggested_value": client.host} if client else None,
            ): str,
            vol.Required(
                CONF_PORT,
                default=CONF_PORT_DEFAULT,  # type: ignore
                description={"suggested_value": client.port} if client else None,
            ): int,
            vol.Optional(
                CONF_USERNAME,
                description={"suggested_value": client.username} if client else None,
            ): str,
            vol.Optional(
                CONF_PASSWORD,
                description={"suggested_value": client.password} if client else None,
            ): str,
            vol.Required(
                CONF_TLS_MODE,
                default=CONF_TLS_MODE_OPTIONS[0],  # type: ignore
                description={"suggested_value": user_input.get(CONF_TLS_MODE)}
                if user_input
                else CONF_TLS_MODE_OPTIONS[0],
            ): vol.In(CONF_TLS_MODE_OPTIONS),
            vol.Optional(
                CONF_WEBHOOK_MODE,
                default=CONF_WEBHOOK_MODE_OPTIONS[0],  # type: ignore
                description={"suggested_value": user_input.get(CONF_WEBHOOK_MODE)}
                if user_input
                else CONF_WEBHOOK_MODE_OPTIONS[0],
            ): vol.In(CONF_WEBHOOK_MODE_OPTIONS),
            vol.Optional(
                CONF_WEBHOOK_ADDRESS,
                default=CONF_WEBHOOK_ADDRESS_OPTIONS[0],  # type: ignore
                description={"suggested_value": user_input.get(CONF_WEBHOOK_ADDRESS)}
                if user_input
                else CONF_WEBHOOK_ADDRESS_OPTIONS[0],
            ): vol.In(CONF_WEBHOOK_ADDRESS_OPTIONS),
            vol.Optional(
                CONF_MEDIASOURCE,
                description={"suggested_value": user_input.get(CONF_MEDIASOURCE)}
                if user_input
                else True,
            ): bool,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(schema), errors=errors
        )


class OptionsFlowHandler(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry):
        self._config_entry = config_entry
        self._data = dict(config_entry.data)

        self._api: MotionHttpClient | None = None  # init later since we don't have hass
        self._config_set = {}  # the actual config(s) of motion cameras

        self._config_id = ""  # camera_id under configuration (async_step_config)
        self._config_section = ""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            selected = user_input.get(CONF_SELECT_FLOW)
            if selected == CONF_OPTION_CONNECTION:
                return await self.async_step_connection()
            elif selected == CONF_OPTION_ALARM:
                return await self.async_step_alarm()
            elif selected in self._config_set.keys():
                # getting here means self._api was retrieved so we can interact with it
                self._config_id = selected
                self._config_section = cs.SECTION_SYSTEM
                return await self.async_step_config()
            else:
                if self._api:
                    await self._api.sync_config()
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=self._data
                )
                return self.async_create_entry(title="", data=None)  # type: ignore

        # cache here since we'll often use this
        if self._api is None:
            self._api = self.hass.data[DOMAIN].get(self._config_entry.entry_id)
            # entry could be not loaded!! (disabled or awaiting initial connection)
            if self._api:
                self._config_set = {
                    _id: "Global motion.conf"
                    if _id == cs.GLOBAL_ID
                    else config.get(cs.CAMERA_NAME, _id)
                    for _id, config in self._api.configs.items()
                }

        options = dict(CONF_SELECT_FLOW_OPTIONS)
        options.update(self._config_set)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SELECT_FLOW,
                        default=CONF_OPTION_NONE,  # type: ignore
                    ): vol.In(options)
                }
            ),
        )

    async def async_step_connection(self, user_input=None):
        errors = {}
        data = self._data

        if user_input is not None:
            client = MotionHttpClient(
                data[CONF_HOST],
                data[CONF_PORT],
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
                tlsmode=MAP_TLS_MODE[
                    user_input.get(CONF_TLS_MODE, CONF_TLS_MODE_OPTIONS[0])
                ],
                session=async_get_clientsession(self.hass),
                logger=LOGGER,
            )

            try:
                await client.update()
            except MotionHttpClientError as err:
                if err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

            await client.close()

            data[CONF_USERNAME] = client.username
            data[CONF_PASSWORD] = client.password
            data[CONF_TLS_MODE] = user_input.get(CONF_TLS_MODE)
            data[CONF_WEBHOOK_MODE] = user_input.get(CONF_WEBHOOK_MODE)
            data[CONF_WEBHOOK_ADDRESS] = user_input.get(CONF_WEBHOOK_ADDRESS)
            data[CONF_MEDIASOURCE] = user_input.get(CONF_MEDIASOURCE)
            if client.is_available:
                return await self.async_step_init()

        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_USERNAME,
                        description={"suggested_value": data.get(CONF_USERNAME)},
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        description={"suggested_value": data.get(CONF_PASSWORD)},
                    ): str,
                    vol.Optional(
                        CONF_TLS_MODE,
                        default=CONF_TLS_MODE_OPTIONS[0],  # type: ignore
                        description={"suggested_value": data.get(CONF_TLS_MODE)},
                    ): vol.In(CONF_TLS_MODE_OPTIONS),
                    vol.Optional(
                        CONF_WEBHOOK_MODE,
                        default=CONF_WEBHOOK_MODE_OPTIONS[0],  # type: ignore
                        description={"suggested_value": data.get(CONF_WEBHOOK_MODE)},
                    ): vol.In(CONF_WEBHOOK_MODE_OPTIONS),
                    vol.Optional(
                        CONF_WEBHOOK_ADDRESS,
                        default=CONF_WEBHOOK_ADDRESS_OPTIONS[0],  # type: ignore
                        description={"suggested_value": data.get(CONF_WEBHOOK_ADDRESS)},
                    ): vol.In(CONF_WEBHOOK_ADDRESS_OPTIONS),
                    vol.Optional(
                        CONF_MEDIASOURCE,
                        description={"suggested_value": data.get(CONF_MEDIASOURCE)},
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_alarm(self, user_input=None):
        errors = {}
        data = self._data.get(CONF_OPTION_ALARM, {})

        if user_input is not None:
            self._data[CONF_OPTION_ALARM] = user_input
            return await self.async_step_init()

        # _config_set would be empty in case we didn't setup self._api ...
        cameras = dict(self._config_set)
        if len(cameras):
            cameras.pop(cs.GLOBAL_ID, None)
        else:  # add what we know so far in case the api is unavailable
            cameras.update(
                {_id: _id for _id in data.get(CONF_ALARM_DISARMHOME_CAMERAS)}
            )
            cameras.update(
                {_id: _id for _id in data.get(CONF_ALARM_DISARMAWAY_CAMERAS)}
            )
            cameras.update(
                {_id: _id for _id in data.get(CONF_ALARM_DISARMNIGHT_CAMERAS)}
            )
            cameras.update(
                {_id: _id for _id in data.get(CONF_ALARM_DISARMBYPASS_CAMERAS)}
            )
        validate_cameras = cv.multi_select(cameras)

        return self.async_show_form(
            step_id="alarm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PIN, description={"suggested_value": data.get(CONF_PIN)}
                    ): str,  # it looks like we cannot serialize other than str, int and few other
                    # it would be nice to have a nice regex here...
                    vol.Optional(
                        CONF_ALARM_DISARMHOME_CAMERAS,
                        description={
                            "suggested_value": data.get(CONF_ALARM_DISARMHOME_CAMERAS)
                        },
                    ): validate_cameras,
                    vol.Optional(
                        CONF_ALARM_DISARMAWAY_CAMERAS,
                        description={
                            "suggested_value": data.get(CONF_ALARM_DISARMAWAY_CAMERAS)
                        },
                    ): validate_cameras,
                    vol.Optional(
                        CONF_ALARM_DISARMNIGHT_CAMERAS,
                        description={
                            "suggested_value": data.get(CONF_ALARM_DISARMNIGHT_CAMERAS)
                        },
                    ): validate_cameras,
                    vol.Optional(
                        CONF_ALARM_DISARMBYPASS_CAMERAS,
                        description={
                            "suggested_value": data.get(CONF_ALARM_DISARMBYPASS_CAMERAS)
                        },
                    ): validate_cameras,
                    vol.Optional(
                        CONF_ALARM_PAUSE_DISARMED,
                        description={
                            "suggested_value": data.get(CONF_ALARM_PAUSE_DISARMED)
                        },
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_config(self, user_input=None):
        errors = {}

        assert self._api

        if user_input is not None:
            for key, value in user_input.items():
                if key == CONF_SELECT_CONFIG:
                    self._config_section = value
                    continue
                try:
                    await self._api.async_config_set(
                        key=key,
                        value=value,
                        id=self._config_id,
                        force=False,
                        persist=False,
                    )
                except Exception as e:
                    errors["base"] = "cannot_connect"
                    LOGGER.warning(
                        "Error (%s) setting motion parameter '%s'", str(e), key
                    )

            if self._config_section == CONF_OPTION_NONE:
                return await self.async_step_init()
            # else load another schema/options to edit

        config = self._api.configs.get(self._config_id, {})
        config_section_map = cs.SECTION_SET_MAP.get(self._config_section)
        schema = {}
        if config_section_map:
            # expose a set of known motion params normalized through config_schema
            config_exclusion_set = (
                cs.CAMERACONFIG_SET
                if self._config_id == cs.GLOBAL_ID
                else cs.GLOBALCONFIG_SET
            )
            for key, descriptor in config_section_map.items():
                if (key in config) and (key not in config_exclusion_set):
                    param = config.get(key)
                    schema[
                        vol.Optional(key, description={"suggested_value": param})
                    ] = _map_motion_cs_validator(
                        descriptor if param is None else param.descriptor
                    )
            """
            schema = {
                vol.Optional(key, description={'suggested_value': config.get(key)})
                : _map_motion_cs_validator(cs.SCHEMA[key])
                for key in config_section_set if (key in config) and (key not in config_exclusion_set)
            }
            """
        else:
            # expose any param we didn't normalize
            # This isnt working fine since the frontend is not able to render an unknown description
            for key in config.keys():
                if key not in cs.SCHEMA.keys():
                    param = config.get(key)
                    schema[
                        vol.Optional(key, description={"suggested_value": param})
                    ] = (
                        str
                        if param is None
                        else _map_motion_cs_validator(param.descriptor)
                    )
            """
            schema = {
                vol.Optional(key, description={'suggested_value': config.get(key)})
                : str
                for key in config.keys() if (key not in cs.SCHEMA.keys())
            }
            """

        schema.update(
            {
                vol.Required(
                    CONF_SELECT_CONFIG,
                    default=CONF_OPTION_NONE,  # type: ignore
                ): vol.In(CONF_SELECT_CONFIG_OPTIONS)
            }
        )

        return self.async_show_form(
            step_id="config",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "camera_id": self._config_set.get(self._config_id),
                "config_section": f"<a href='{_get_config_section_url(self._api.version, self._config_section)}'>"
                f"{CONF_SELECT_CONFIG_OPTIONS[self._config_section]}</a>",
            },
            errors=errors,
        )
