"""Config flow to configure Agent devices."""
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    ConfigFlow, OptionsFlow
)
from homeassistant.const import (
    CONF_HOST, CONF_PORT,
    CONF_USERNAME, CONF_PASSWORD
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .motionclient import MotionHttpClient, MotionHttpClientConnectionError, MotionHttpClientError

from .helpers import (
    LOGGER
    #generate_url
)

from .const import (
    DOMAIN, CONF_PORT_DEFAULT,
    #CONF_OPTION_NONE, CONF_OPTION_DEFAULT, CONF_OPTION_AUTO,
    CONF_TLS_MODE, CONF_TLS_MODE_OPTIONS, MAP_TLS_MODE,
    CONF_WEBHOOK_MODE, CONF_WEBHOOK_MODE_OPTIONS,
    CONF_WEBHOOK_ADDRESS, CONF_WEBHOOK_ADDRESS_OPTIONS,
    CONF_MEDIASOURCE
)


class MotionFlowHandler(ConfigFlow, domain=DOMAIN):

    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH
    VERSION = 1


    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


    async def async_step_user(self, user_input=None):

        errors = {}
        client: MotionHttpClient = None

        if user_input is not None:

            client = MotionHttpClient(user_input[CONF_HOST], user_input[CONF_PORT],
                username=user_input.get(CONF_USERNAME), password= user_input.get(CONF_PASSWORD),
                tlsmode=MAP_TLS_MODE[user_input.get(CONF_TLS_MODE, CONF_TLS_MODE_OPTIONS[0])],
                session=async_get_clientsession(self.hass),
                logger=LOGGER
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
            vol.Required(CONF_HOST, default="localhost",
                description={"suggested_value": client.host} if client else None)
                : str,
            vol.Required(CONF_PORT, default=CONF_PORT_DEFAULT,
                description={"suggested_value": client.port} if client else None)
                : int,
            vol.Optional(CONF_USERNAME,
                description={"suggested_value": client.username} if client else None)
                : str,
            vol.Optional(CONF_PASSWORD,
                description={"suggested_value": client.password} if client else None)
                : str,
            vol.Required(CONF_TLS_MODE, default=CONF_TLS_MODE_OPTIONS[0],
                description={"suggested_value": user_input.get(CONF_TLS_MODE)} if user_input else CONF_TLS_MODE_OPTIONS[0])
                : vol.In(CONF_TLS_MODE_OPTIONS),
            vol.Optional(CONF_WEBHOOK_MODE, default=CONF_WEBHOOK_MODE_OPTIONS[0],
                description={"suggested_value": user_input.get(CONF_WEBHOOK_MODE)} if user_input else CONF_WEBHOOK_MODE_OPTIONS[0])
                : vol.In(CONF_WEBHOOK_MODE_OPTIONS),
            vol.Optional(CONF_WEBHOOK_ADDRESS, default=CONF_WEBHOOK_ADDRESS_OPTIONS[0],
                description={"suggested_value": user_input.get(CONF_WEBHOOK_ADDRESS)} if user_input else CONF_WEBHOOK_ADDRESS_OPTIONS[0])
                : vol.In(CONF_WEBHOOK_ADDRESS_OPTIONS),
            vol.Optional(CONF_MEDIASOURCE,
                description={"suggested_value": user_input.get(CONF_MEDIASOURCE)} if user_input else True)
                : bool
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        )



class OptionsFlowHandler(OptionsFlow):

    def __init__(self, config_entry):
        self._config_entry = config_entry


    async def async_step_init(self, user_input=None):
        errors = {}
        data = self._config_entry.data

        if user_input is not None:

            client = MotionHttpClient(data[CONF_HOST], data[CONF_PORT],
                username=user_input.get(CONF_USERNAME), password= user_input.get(CONF_PASSWORD),
                tlsmode=MAP_TLS_MODE[user_input.get(CONF_TLS_MODE, CONF_TLS_MODE_OPTIONS[0])],
                session=async_get_clientsession(self.hass),
                logger=LOGGER
                )

            try:
                await client.update()
            except MotionHttpClientError as err:
                if err.status == 401:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

            await client.close()

            data = dict(data)
            data[CONF_USERNAME] = client.username
            data[CONF_PASSWORD] = client.password
            data[CONF_TLS_MODE] = user_input.get(CONF_TLS_MODE)
            data[CONF_WEBHOOK_MODE] = user_input.get(CONF_WEBHOOK_MODE)
            data[CONF_WEBHOOK_ADDRESS] = user_input.get(CONF_WEBHOOK_ADDRESS)
            data[CONF_MEDIASOURCE] = user_input.get(CONF_MEDIASOURCE)
            if client.is_available:
                self.hass.config_entries.async_update_entry(self._config_entry, data=data)
                return self.async_create_entry(title="", data=None)

        schema = {
            vol.Optional(CONF_USERNAME,
                description={"suggested_value": data.get(CONF_USERNAME)})
                : str,
            vol.Optional(CONF_PASSWORD,
                description={"suggested_value": data.get(CONF_PASSWORD)})
                : str,
            vol.Optional(CONF_TLS_MODE, default=CONF_TLS_MODE_OPTIONS[0],
                description={"suggested_value": data.get(CONF_TLS_MODE)})
                : vol.In(CONF_TLS_MODE_OPTIONS),
            vol.Optional(CONF_WEBHOOK_MODE, default=CONF_WEBHOOK_MODE_OPTIONS[0],
                description={"suggested_value": data.get(CONF_WEBHOOK_MODE)})
                : vol.In(CONF_WEBHOOK_MODE_OPTIONS),
            vol.Optional(CONF_WEBHOOK_ADDRESS, default=CONF_WEBHOOK_ADDRESS_OPTIONS[0],
                description={"suggested_value": data.get(CONF_WEBHOOK_ADDRESS)})
                : vol.In(CONF_WEBHOOK_ADDRESS_OPTIONS),
            vol.Optional(CONF_MEDIASOURCE,
                description={"suggested_value": data.get(CONF_MEDIASOURCE)})
                : bool
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
