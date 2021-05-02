"""An Http API Client to interact with motion server"""
import logging
from typing import List, Optional, Dict, Any, Callable, Union
from urllib.parse import urljoin
from enum import Enum
from html.parser import HTMLParser

import re
import aiohttp
from yarl import URL
import socket
import asyncio
import async_timeout


from datetime import datetime


class MotionHttpClientError(Exception):
    def __init__(self, status: Optional[int], message: Optional[str]):  # pylint: disable=unsubscriptable-object
        self.status = status
        self.message = message
        self.args = (status, message)


class MotionHttpClientConnectionError(MotionHttpClientError):
    pass


class TlsMode(Enum):
    AUTO = 0 # tries to adapt to server responses enabling e 'best effort' behaviour
    NONE = 1 # no TLS at all
    RELAXED = 2 # use TLS but accept any certificate
    STRICT = 3 # use TLS with all the goodies (based on default aiohttp SSL policy)


"""
    default MotionCamera builder: this can be overriden by passing a similar function
    into MotionHttpClient constructor
"""
def _default_camera_factory(client: "MotionHttpClient", id: int) -> "MotionCamera":
    return MotionCamera(client, id)


class MotionHttpClient:

    DEFAULT_TIMEOUT = 10

    def __init__(self, host, port,
            username = None, password = None,
            tlsmode: TlsMode = TlsMode.AUTO,
            session: aiohttp.client.ClientSession = None,
            logger: logging.Logger = None,
            camera_factory: Callable[["MotionHttpClient", int], "MotionCamera"] = _default_camera_factory):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._auth = aiohttp.BasicAuth(login=username, password=password) if username and password else None
        self._tlsmode: TlsMode = tlsmode
        self._session = session or aiohttp.ClientSession()
        self._logger = logger or logging.getLogger(__name__)
        self._camera_factory = camera_factory
        self._server_url = None # established only on first succesful connection
        self._close_session = (session is None)
        self._conFailed = False
        self.disconnected = datetime.now()
        self.reconnect_interval = 10
        self._regex_pattern_config_html = re.compile(r">(\w+)<\/a> = (.*)<\/li>")
        self._regex_pattern_config_text = re.compile(r"(\w+)\s*=\s*(.*?)\s*\n")
        self._version = "unknown"
        self._ver_major = 0
        self._ver_minor = 0
        self._ver_build = 0
        self._feature_webhtml = False # report if the webctrl server is configured for html
        self._feature_advancedstream = False # if True (from ver 4.2 on) allows more uri options and multiple streams on the same port
        self._feature_tls = False
        self._feature_globalactions = False # if True (from ver 4.2 on) we can globally start/pause detection by issuing on threadid = 0
        self._configs : Dict[int, Dict[str, Any]] = {}
        self._cameras : Dict[int, 'MotionCamera'] = {}
        self._requestheaders = {
            "User-Agent": "HomeAssistant Motion Frontend",
            "Accept": "*/*"
            }
        self._server_url = MotionHttpClient.generate_url(
            self._host,
            self._port,
            "http" if self._tlsmode in (TlsMode.AUTO, TlsMode.NONE) else "https"
            )


    @staticmethod
    def generate_url(host, port, proto = "http") -> str:
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
        return f'{self._host}_{self._port}'


    @property
    def name(self) -> str:
        return f'motion@{self._host}'


    @property
    def description(self) -> str:
        return self._description


    @property
    def version(self) -> str:
        return self._version


    @property
    def server_url(self) -> str:
        return self._server_url


    @property
    def stream_url(self) -> str:
        return MotionHttpClient.generate_url(
            self._host,
            self.config.get("stream_port", 8081),
            "https" if self.config.get("stream_tls", False) else "http"
            )


    @property
    def config(self) -> Dict[str, Any]:
        return self._configs.get(0)


    @property
    def cameras(self) -> Dict[str, 'MotionCamera']:
        return self._cameras


    def getcamera(self, camera_id) -> 'MotionCamera':
        for camera in self._cameras.values():
            if camera.camera_id == camera_id:
                return camera
        return None


    async def close(self) -> None:
        if self._session and self._close_session:
            await self._session.close()


    async def update(self, updatecameras: bool = False):
        content, _ = await self.async_request("/")

        self._cameras.clear()
        self._configs.clear()

        async def add_camera(id: int):
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
                await add_camera(int(i))

            tags = re.findall(r"<a href='\/(\d+)\/'>Camera", content)
            for i in tags:
                await add_camera(int(i))

        else:
            lines = content.splitlines()
            self._description = lines[0]
            numlines = len(lines)
            i = 1
            while i < numlines:
                cfg_id = int(lines[i].strip())
                i = i + 1
                if (cfg_id == 0) and (i < numlines):
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

        if 0 not in self._configs.keys():
            self._configs[0] = await self.async_config_list(0)

        # here we're not relying on self._version being correctly parsed
        # since the matching code could fail in future
        # I prefer to rely on a well known config param which should be more stable
        self._feature_tls = ("webcontrol_tls" in self.config)
        self._feature_advancedstream = self._feature_tls # these appear at the same time ;)
        self._feature_globalactions = self._feature_tls

        if updatecameras: # request also camera status
            await self.async_detection_status()

        return


    async def async_config_list(self, id) -> Dict[str, Any]:
        config = {}
        content, _ = await self.async_request(f"/{id}/config/list")
        if content:
            try:
                if content.startswith("<!DOCTYPE html>"):
                    config = dict(self._regex_pattern_config_html.findall(content))
                else:
                    config = dict(self._regex_pattern_config_text.findall(content))
                for key, value in config.items():
                    if value in ("(not defined)", "(null)"):
                        config[key] = None
                    elif value == "on":
                        config[key] = True
                    elif value == "off":
                        config[key] = False
                    elif value.lstrip("-").isnumeric():
                        config[key] = int(value)

            except Exception as e:
                self._logger.warning(str(e))
                pass

        return config


    async def async_config_set(self, param: str, value: Any, force: bool = False, persist: bool = False, id: int = 0):

        config = self._configs.get(id)
        if (force is False) and config and (config.get(param) == value):
            return

        await self.async_request(f"/{id}/config/set?{param}={value}")

        if persist:
            await self.async_request(f"/{id}/config/write")

        if config:
            config[param] = value

        return


    async def async_detection_status(self, id: int = 0) -> None:
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
                    self.getcamera(int(match.group(1)))._setconnected(match.group(2) == "OK")
                except Exception as exception:
                    self._logger.warning(str(exception))
        except Exception as exception:
            self._logger.warning(str(exception))

        try:
            content: str = ""
            if id or self._feature_globalactions:
                #recover all cameras in 1 pass
                content, _ = await self.async_request(f"/{id}/detection/status")
            else:
                for _id in self.cameras.keys():
                    addcontent, _ = await self.async_request(f"/{_id}/detection/status")
                    content += addcontent
            for match in re.finditer(r"\s*(\d+).*(ACTIVE|PAUSE)", content):
                try:
                    self.getcamera(int(match.group(1)))._setpaused(match.group(2) == "PAUSE")
                except Exception as exception:
                    self._logger.warning(str(exception))
        except Exception as exception:
            self._logger.warning(str(exception))

        return


    async def async_detection_start(self, id: int = None):
        try:
            if id or self._feature_globalactions:
                response, _ = await self.async_request(f"/{id or 0}/detection/start")
                # we might get a response or not...(html mode doesnt?)
                paused = False # optimistic: should be instead invoke detection_status?
                if "paused" in response:
                    # not sure if it happens that the command fails on motion and
                    # we still get a response. This is a guess
                    paused = True
                if id:
                    self._cameras[id]._setpaused(paused)
                else:
                    for camera in self._cameras.values():
                        camera._setpaused(paused)
            else:
                for _id in self._cameras:
                    await self.async_detection_start(_id)

        except Exception as exception:
            self._logger.warning(str(exception))


    async def async_detection_pause(self, id: int = None):
        try:
            if id or self._feature_globalactions:
                response, _ = await self.async_request(f"/{id or 0}/detection/pause")
                # we might get a response or not...(html mode doesnt?)
                paused = True # optimistic: should be instead invoke detection_status?
                if "resumed" in response:
                    # not sure if it happens that the command fails on motion and
                    # we still get a response. This is a guess
                    paused = False
                if id:
                    self._cameras[id]._setpaused(paused)
                else:
                    for camera in self._cameras.values():
                        camera._setpaused(paused)
            else:
                for _id in self._cameras:
                    await self.async_detection_pause(_id)

        except Exception as exception:
            self._logger.warning(str(exception))


    async def async_request(self, api_url, timeout=DEFAULT_TIMEOUT) -> str:
        if self._conFailed:
            if (datetime.now()-self.disconnected).total_seconds() < self.reconnect_interval:
                return None

        def _raise(exception, status, message):
            self.disconnected = datetime.now()
            self._conFailed = True
            raise MotionHttpClientConnectionError(status, message) from exception

        looptry = 0
        while True:
            try:
                with async_timeout.timeout(timeout):
                    url = URL(self._server_url + api_url)
                    response = await self._session.request(
                        "GET",
                        url,
                        auth=self._auth,
                        headers=self._requestheaders,
                        ssl=self._tlsmode is TlsMode.STRICT
                    )
                    response.raise_for_status()
            except asyncio.TimeoutError as exception:
                _raise(exception, -1, "Timeout occurred while connecting to motion http interface")
            except (
                aiohttp.ClientError,
                aiohttp.ClientResponseError,
            ) as exception:
                message = str(exception)
                status = -1
                if hasattr(exception, 'message'):
                    message = exception.message
                    if hasattr(message, 'code'):
                        status = message.code
                    if hasattr(message, 'reason'):
                        message = message.reason
                if (status == -1) and (looptry == 0) and (self._tlsmode is TlsMode.AUTO): # it should be an aiohttp.ServerDisconnectedError
                    if self._server_url.startswith("http:"):
                        self._server_url = MotionHttpClient.generate_url(self._host, self._port, "https")
                    else:
                        self._server_url = MotionHttpClient.generate_url(self._host, self._port, "http")
                    looptry = 1
                    continue # dirty flow behaviour: restart the request loop
                _raise(exception, status, message)
            except (
                Exception,
                socket.gaierror,
            ) as exception:
                _raise(exception, -1, "Error occurred while communicating with motion server")

            text = await response.text()
            self._conFailed = False
            return text, response.headers



class MotionCamera:

    def __init__(self, client: MotionHttpClient, id: int):
        self._client : MotionHttpClient = client
        self._id: int = id
        self._connected = False # netcam connected in 'motion' terms
        self._paused = False # detection paused in 'motion' terms


    @property
    def client(self) -> MotionHttpClient:
        return self._client


    @property
    def id(self) -> str:
        return self._id

    @property
    def camera_id(self) -> int:
        """
        camera_id has different usages among motion versions:
        in recent webctrl it looks like camera_id is used to build url path to access cameras
        while in legacy webctrl it appears here and there (some labels in webctrl responses)
        example GET /0/detection/connection returns the camera list enumerating cameras and labelling by camera_id
        for this reason, in order to correctly match a camera we need this 'hybrid' since camera_id usually defaults
        to the motion thread_id when not explicitly configured
        """
        return self.config.get("camera_id", id)


    @property
    def connected(self) -> bool:
        return self._connected
    def _setconnected(self, connected: bool):
        if self._connected != connected:
            self._connected = connected
            self.on_connected_changed()
    def on_connected_changed(self):
        pass # stub -> override or whatever to manage notification


    @property
    def paused(self) -> bool:
        return self._paused
    def _setpaused(self, paused: bool):
        if self._paused != paused:
            self._paused = paused
            self.on_paused_changed()
    def on_paused_changed(self):
        pass # stub -> override or whatever to manage notification

    @property
    def config(self) -> Dict[str, object]:
        return self._client._configs.get(self._id)


    @property
    def config_url(self) -> str:
        return f"{self._client.server_url}/{self._id}"


    # MJPEG live stream
    @property
    def stream_url(self) -> str:
        port = self.config.get("stream_port")
        if port:
            return f"{MotionHttpClient.generate_url(self._client._host, port)}"
        else:
            return f"{self._client.stream_url}/{self._id}/stream"

    # JPEG currentsnapshot
    @property
    def image_url(self) -> str:
        if not self._client._feature_advancedstream:
            return None

        port = self.config.get("stream_port")
        if port:
            return f"{MotionHttpClient.generate_url(self._client._host, port)}/current"
        else:
            return f"{self._client.stream_url}/{self._id}/current"


    async def async_config_set(self, param: str, value: Any, force: bool = False, persist: bool = False):
        await self._client.async_config_set(param=param, value=value, force=force, persist=persist, id=self._id)


    async def async_makemovie(self):
        await self._client.async_request(f"/{self._id}/action/makemovie")


    async def async_snapshot(self):
        await self._client.async_request(f"/{self._id}/action/snapshot")
