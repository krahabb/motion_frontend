"""An Http API Client to interact with motion server"""

import asyncio
from datetime import datetime
from enum import Enum
import logging
import re
import socket
import typing

import aiohttp
from yarl import URL

from . import config_schema as cs


class MotionHttpClientError(Exception):
    def __init__(
        self,
        client: "MotionHttpClient",
        message: str | None,
        path: str | None,
        status: int | None,
    ):  # pylint: disable=unsubscriptable-object
        self.message = message
        self.status = status
        self.client = client
        self.args = (message, status, client.server_url, path)


class MotionHttpClientConnectionError(MotionHttpClientError):
    pass


class TlsMode(Enum):
    AUTO = 0  # tries to adapt to server responses enabling e 'best effort' behaviour
    NONE = 1  # no TLS at all
    RELAXED = 2  # use TLS but accept any certificate
    STRICT = 3  # use TLS with all the goodies (based on default aiohttp SSL policy)


"""
    default MotionCamera builder: this can be overriden by passing a similar function
    into MotionHttpClient constructor
"""


def _default_camera_factory(client: "MotionHttpClient", id: str):
    return MotionCamera(client, id)


class MotionHttpClient:
    DEFAULT_TIMEOUT = (
        5  # use a lower than 10 timeout in order to not annoy HA update cycle
    )

    def __init__(
        self,
        host,
        port,
        username=None,
        password=None,
        tlsmode: TlsMode = TlsMode.AUTO,
        session: aiohttp.ClientSession | None = None,
        logger: logging.Logger | None = None,
        camera_factory: "typing.Callable[[MotionHttpClient, str], MotionCamera]" = _default_camera_factory,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._auth = (
            aiohttp.BasicAuth(login=username, password=password)
            if username and password
            else None
        )
        self._tlsmode: TlsMode = tlsmode
        self._session = session or aiohttp.ClientSession()
        self._logger = logger or logging.getLogger(__name__)
        self._camera_factory = camera_factory
        self._close_session = session is None
        self._conFailed = False
        self.disconnected = datetime.now()
        self.reconnect_interval = 10
        self._regex_pattern_config_html = re.compile(r">(\w+)<\/a> = (.*)<\/li>")
        self._regex_pattern_config_text = re.compile(r"(\w+)\s*=\s*(.*?)\s*\n")
        self._version = "unknown"
        self._ver_major = 0
        self._ver_minor = 0
        self._ver_build = 0
        self._feature_webhtml = (
            False  # report if the webctrl server is configured for html
        )
        self._feature_advancedstream = False  # if True (from ver 4.2 on) allows more uri options and multiple streams on the same port
        self._feature_tls = False
        self._feature_globalactions = False  # if True (from ver 4.2 on) we can globally start/pause detection by issuing on threadid = 0
        self._configs: dict[str, dict[str, cs.AnyParam]] = {}
        self._cameras: dict[str, "MotionCamera"] = {}
        self._config_is_dirty = (
            False  # set when we modify a motion config param (async_config_set)
        )
        self._config_need_restart = set()
        self._requestheaders = {
            "User-Agent": "HomeAssistant Motion Frontend",
            "Accept": "*/*",
        }
        self._server_url = MotionHttpClient.generate_url(
            self._host,
            self._port,
            "http" if self._tlsmode in (TlsMode.AUTO, TlsMode.NONE) else "https",
        )

    @staticmethod
    def generate_url(host, port, proto="http") -> str:
        return f"{proto}://{host}:{port}"

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def tlsmode(self) -> TlsMode:
        return self._tlsmode

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def is_available(self) -> bool:
        return not self._conFailed

    @property
    def unique_id(self) -> str:
        return f"{self._host}_{self._port}"

    @property
    def name(self) -> str:
        return f"motion@{self._host}"

    @property
    def description(self) -> str:
        return self._description

    @property
    def version(self) -> str:
        return self._version

    @property
    def config_is_dirty(self) -> bool:
        return self._config_is_dirty

    @property
    def server_url(self) -> str:
        return self._server_url

    @property
    def stream_url(self) -> str:
        return MotionHttpClient.generate_url(
            self._host,
            self.config.get(cs.STREAM_PORT, 8081),
            "https" if self.config.get(cs.STREAM_TLS, False) else "http",
        )

    @property
    def configs(
        self,
    ):
        return self._configs

    @property
    def config(self):
        return self._configs.get(cs.GLOBAL_ID, {})

    @property
    def cameras(self):
        return self._cameras

    def getcamera(self, camera_id: str) -> "MotionCamera":
        for camera in self._cameras.values():
            if camera.camera_id == camera_id:
                return camera
        raise Exception(f"Camera with id={camera_id} not found")

    async def close(self) -> None:
        if self._session and self._close_session:
            await self._session.close()

    async def update(self, updatecameras: bool = False):
        content, _ = await self.async_request("/")

        self._cameras.clear()
        self._configs.clear()

        self._configs[cs.GLOBAL_ID] = await self.async_config_list(cs.GLOBAL_ID)

        async def add_camera(id: str):
            self._configs[id] = await self.async_config_list(id)
            self._cameras[id] = self._camera_factory(self, id)
            return

        # checking content_type is not reliable since
        # motion (4.3.3 at least..probably since new webctrl interface in 4.2)
        # returns plain text with text/html content_type
        if content.startswith("<!DOCTYPE html>"):
            match_title = re.search(r"<title>(.*)<\/title>", content)
            if match_title:
                self._description = match_title.group(1)

            tags = re.findall(r"camera_click\('cam_(\d+)'", content)
            for i in tags:
                await add_camera(i)

            tags = re.findall(r"<a href='\/(\d+)\/'>Camera", content)
            for i in tags:
                await add_camera(i)

        else:
            lines = content.splitlines()
            self._description = lines[0]
            numlines = len(lines)
            i = 1
            while i < numlines:
                cfg_id = lines[i].strip()
                i = i + 1
                if (cfg_id == cs.GLOBAL_ID) and (i < numlines):
                    continue
                await add_camera(cfg_id)

        if match_version := re.search(r"Motion ([\w\.]+)", content):
            self._version = match_version.group(1)

        if match_version := re.search(r"(\d+)\.*(\d*)\.*(\d*)", self._version):
            count = len(match_version.regs)
            if count > 1:
                self._ver_major = int(match_version.group(1))
            if count > 2:
                self._ver_minor = int(match_version.group(2))
            if count > 3:
                self._ver_build = int(match_version.group(3))

        # here we're not relying on self._version being correctly parsed
        # since the matching code could fail in future
        # I prefer to rely on a well known config param which should be more stable
        self._feature_tls = cs.WEBCONTROL_TLS in self.config
        self._feature_advancedstream = (
            self._feature_tls
        )  # these appear at the same time ;)
        self._feature_globalactions = self._feature_tls

        if updatecameras:  # request also camera status
            await self.async_detection_status()

    async def sync_config(self) -> None:
        """
        Checks if we have pending changes to motion config(s)
        and instruct the daemon to write config to filesystem
        also checks if some (or all) threads need a restart to
        reload changed configs (some config param changes work
        on the fly some other dont)
        """
        if self.config_is_dirty:
            await self.async_config_write()
            if cs.GLOBAL_ID in self._config_need_restart:
                await self.async_action_restart(cs.GLOBAL_ID)
            else:
                for _id in frozenset(self._config_need_restart):
                    await self.async_action_restart(_id)

    async def async_config_list(self, id) -> dict[str, cs.AnyParam]:
        config = {}
        content, _ = await self.async_request(f"/{id}/config/list")
        if content:
            try:
                if content.startswith("<!DOCTYPE html>"):
                    config = dict(self._regex_pattern_config_html.findall(content))
                else:
                    config = dict(self._regex_pattern_config_text.findall(content))
                for key, value in config.items():
                    try:
                        config[key] = cs.build_value(key, value)
                    except Exception as e:
                        self._logger.warning(str(e))
                        config[key] = value

            except Exception as e:
                self._logger.warning(str(e))
                pass

        return config

    async def async_config_set(
        self,
        key: str,
        value: typing.Any,
        force: bool = False,
        persist: bool = False,
        id: str = cs.GLOBAL_ID,
    ):
        config = self._configs.get(id)
        if (force is False) and config and (config.get(key) == value):
            return

        newvalue = cs.build_value(key, value)
        await self.async_request(f"/{id}/config/set?{key}={newvalue.__str__()}")

        if (
            id == cs.GLOBAL_ID
        ):  # motion will set all threads with this same value when setting global conf
            for config in self._configs.values():
                if key in config:  # some params are only relevant to global conf
                    config[key] = newvalue
        else:
            if config:
                config[key] = newvalue

        self._config_is_dirty = True
        if key in cs.RESTARTCONFIG_SET:
            self._config_need_restart.add(id)

        if persist:
            await self.async_config_write()

    async def async_config_write(self) -> None:
        """
        Motion saves all of the configs in 1 call: no option to differentiate atm
        """
        await self.async_request(f"/0/config/writeyes")
        self._config_is_dirty = False

    async def async_action_restart(self, id: str = cs.GLOBAL_ID) -> None:
        await self.async_request(f"/{id}/action/restart")
        if id == cs.GLOBAL_ID:
            # restarting thread 0 will restart all of motion
            self._config_need_restart.clear()
        else:
            self._config_need_restart.discard(id)

    async def async_detection_status(self, id: str = cs.GLOBAL_ID) -> None:
        """
        When we want to poll the status (even for a single camera)
        we'll try to optmize and just request the full camera list states
        in order to not 'strike' the server webctrl with a load of requests

        id - is an hint on which camera wants an update in order
        to handle legacy webctrl which doesnt support full list query

        Note on exceptions: at the moment we're trying our best to make this run
        until the end 'silencing' intermediate exceptions and just warning
        this is not a critical feature so we can live without it
        """
        try:
            content, _ = await self.async_request(f"/{id}/detection/connection")
            for match in re.finditer(r"\s*(\d+).*(OK|Lost).*\n", content):
                try:
                    self.getcamera(match.group(1))._setconnected(match.group(2) == "OK")
                except Exception as exception:
                    self._logger.warning(
                        "exception (%s) in async_detection_status", str(exception)
                    )

            if (id != cs.GLOBAL_ID) or self._feature_globalactions:
                # recover all cameras in 1 pass
                content, _ = await self.async_request(f"/{id}/detection/status")
            else:
                content: str = ""
                for _id in self.cameras.keys():
                    addcontent, _ = await self.async_request(f"/{_id}/detection/status")
                    content += addcontent
            for match in re.finditer(r"\s*(\d+).*(ACTIVE|PAUSE)", content):
                try:
                    self.getcamera(match.group(1))._setpaused(match.group(2) == "PAUSE")
                except Exception as exception:
                    self._logger.warning(
                        "exception (%s) in async_detection_status", str(exception)
                    )
        except Exception as exception:
            self._logger.info(
                "exception (%s) in async_detection_status", str(exception)
            )

    async def async_detection_start(self, id: str = cs.GLOBAL_ID):
        try:
            if (id != cs.GLOBAL_ID) or self._feature_globalactions:
                response, _ = await self.async_request(f"/{id}/detection/start")
                # we might get a response or not...(html mode doesnt?)
                paused = False  # optimistic: should be instead invoke detection_status?
                if "paused" in response:
                    # not sure if it happens that the command fails on motion and
                    # we still get a response. This is a guess
                    paused = True
                if id != cs.GLOBAL_ID:
                    self._cameras[id]._setpaused(paused)
                else:
                    for camera in self._cameras.values():
                        camera._setpaused(paused)
            else:
                for _id in self._cameras.keys():
                    await self.async_detection_start(_id)

        except Exception as exception:
            self._logger.warning(str(exception))

    async def async_detection_pause(self, id: str = cs.GLOBAL_ID):
        try:
            if (id != cs.GLOBAL_ID) or self._feature_globalactions:
                response, _ = await self.async_request(f"/{id}/detection/pause")
                # we might get a response or not...(html mode doesnt?)
                paused = True  # optimistic: should be instead invoke detection_status?
                if "resumed" in response:
                    # not sure if it happens that the command fails on motion and
                    # we still get a response. This is a guess
                    paused = False
                if id != cs.GLOBAL_ID:
                    self._cameras[id]._setpaused(paused)
                else:
                    for camera in self._cameras.values():
                        camera._setpaused(paused)
            else:
                for _id in self._cameras.keys():
                    await self.async_detection_pause(_id)

        except Exception as exception:
            self._logger.warning(str(exception))

    async def async_request(self, api_url, timeout=DEFAULT_TIMEOUT):
        if self._conFailed:
            if (
                datetime.now() - self.disconnected
            ).total_seconds() < self.reconnect_interval:
                raise MotionHttpClientConnectionError(
                    self, "Connection failed. Retry in few seconds..", api_url, -1
                )

        def _raise(exception, message, status=-1):
            self.disconnected = datetime.now()
            self._conFailed = True
            raise MotionHttpClientConnectionError(
                self, message, api_url, status
            ) from exception

        looptry = 0
        while True:
            try:
                async with asyncio.timeout(timeout):
                    url = URL(self._server_url + api_url)
                    response = await self._session.request(
                        "GET",
                        url,
                        auth=self._auth,
                        headers=self._requestheaders,
                        ssl=self._tlsmode is TlsMode.STRICT,
                    )
                    response.raise_for_status()
                    text = await response.text()
                    self._conFailed = False
                    return text, response.headers

            except asyncio.TimeoutError as exception:
                _raise(
                    exception,
                    "Timeout occurred while connecting to motion http interface",
                )
            except (
                aiohttp.ClientError,
                aiohttp.ClientResponseError,
            ) as exception:
                message = str(exception)
                status = -1
                if hasattr(exception, "message"):
                    message = exception.message  # type: ignore
                    if hasattr(message, "code"):
                        status = message.code  # type: ignore
                    if hasattr(message, "reason"):
                        message = message.reason  # type: ignore
                if (
                    (status == -1)
                    and (looptry == 0)
                    and (self._tlsmode is TlsMode.AUTO)
                ):  # it should be an aiohttp.ServerDisconnectedError
                    if self._server_url.startswith("http:"):
                        self._server_url = MotionHttpClient.generate_url(
                            self._host, self._port, "https"
                        )
                    else:
                        self._server_url = MotionHttpClient.generate_url(
                            self._host, self._port, "http"
                        )
                    looptry = 1
                    continue  # dirty flow behaviour: restart the request loop
                _raise(exception, message, status)
            except (
                Exception,
                socket.gaierror,
            ) as exception:
                _raise(
                    exception, "Error occurred while communicating with motion server"
                )


class MotionCamera:
    def __init__(self, client: "MotionHttpClient", id: str):
        self._client = client
        self._id = id
        self._connected = False  # netcam connected in 'motion' terms
        self._paused = False  # detection paused in 'motion' terms

    @property
    def client(self):
        return self._client

    @property
    def id(self):
        return self._id

    @property
    def camera_id(self):
        """
        camera_id has different usages among motion versions:
        in recent webctrl it looks like camera_id is used to build url path to access cameras
        while in legacy webctrl it appears here and there (some labels in webctrl responses)
        example GET /0/detection/connection returns the camera list enumerating cameras and labelling by camera_id
        for this reason, in order to correctly match a camera we need this 'hybrid' since camera_id usually defaults
        to the motion thread_id when not explicitly configured
        """
        return str(self.config.get(cs.CAMERA_ID, self._id))

    @property
    def connected(self):
        return self._connected

    def _setconnected(self, connected: bool):
        if self._connected != connected:
            self._connected = connected
            self.on_connected_changed()

    def on_connected_changed(self):
        pass  # stub -> override or whatever to manage notification

    @property
    def paused(self):
        return self._paused

    @paused.setter
    def paused(self, paused: bool):
        if self._paused != paused:
            if paused:
                asyncio.create_task(self._client.async_detection_pause(self._id))
            else:
                asyncio.create_task(self._client.async_detection_start(self._id))

    def _setpaused(self, paused: bool):
        if self._paused != paused:
            self._paused = paused
            self.on_paused_changed()

    def on_paused_changed(self):
        pass  # stub -> override or whatever to manage notification

    @property
    def config(self):
        return self._client._configs.get(self._id, {})

    @property
    def config_url(self):
        return f"{self._client.server_url}/{self._id}"

    # MJPEG live stream
    @property
    def stream_url(self):
        port = self.config.get(cs.STREAM_PORT)
        if port:
            return f"{MotionHttpClient.generate_url(self._client._host, port)}"
        else:
            return f"{self._client.stream_url}/{self._id}/stream"

    # JPEG currentsnapshot
    @property
    def image_url(self):
        if not self._client._feature_advancedstream:
            return None

        port = self.config.get(cs.STREAM_PORT)
        if port:
            proto = "https" if self.config.get(cs.STREAM_TLS, False) else "http"
            return f"{MotionHttpClient.generate_url(self._client._host, port, proto)}/current"
        else:
            return f"{self._client.stream_url}/{self._id}/current"

    @property
    def stream_authentication(self):
        """
        return a valid pair of credentials for streaming purposes
        Tryes to match what the motion daemon is especting since
        this is usually a global conf param but you can set it per camera aswell
        (at least in some releases?)
        """
        stream_authentication = self.config.get(cs.STREAM_AUTHENTICATION)
        if not stream_authentication:
            stream_authentication = self._client.config.get(
                cs.STREAM_AUTHENTICATION, ":"
            )
        return str(stream_authentication).split(":")

    async def async_config_set(
        self, key: str, value: typing.Any, force: bool = False, persist: bool = False
    ):
        await self._client.async_config_set(
            key=key, value=value, force=force, persist=persist, id=self._id
        )

    async def async_makemovie(self):
        await self._client.async_request(f"/{self._id}/action/makemovie")

    async def async_snapshot(self):
        await self._client.async_request(f"/{self._id}/action/snapshot")
