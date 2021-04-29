"""An Http API Client to interact with motion server"""
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin
from enum import Enum
from html.parser import HTMLParser

import re
import aiohttp
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


class MotionHttpClient:

    DEFAULT_TIMEOUT = 10

    def __init__(self, host, port,
            username = None, password = None,
            tlsmode: TlsMode = TlsMode.AUTO,
            session: aiohttp.client.ClientSession = None,
            logger: logging.Logger = None):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._auth = aiohttp.BasicAuth(login=username, password=password) if username and password else None
        self._tlsmode: TlsMode = tlsmode
        self._session = session or aiohttp.ClientSession()
        self._logger = logger or logging.getLogger(__name__)
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


    def __getattr__(self, attr):
        return self._configs[0][attr]


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
    def unique_id(self) -> str:
        return f'{self._host}_{self._port}'


    @property
    def is_available(self) -> bool:
        return not self._conFailed


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


    def getcamera(self, camera_id):
        for camera in self._cameras.values():
            if camera.camera_id == camera_id:
                return camera
        return None

    async def close(self) -> None:
        if self._session and self._close_session:
            await self._session.close()


    async def update(self, updatecameras: bool = False):
        content, headers = await self._request("/")

        self._cameras.clear()
        self._configs.clear()

        async def add_camera(id: int):
            self._configs[id] = await self.config_list(id)
            self._cameras[id] = MotionCamera(self, id)
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
            self._configs[0] = await self.config_list(0)

        self._feature_tls = ("webcontrol_tls" in self.config)
        self._feature_advancedstream = self._feature_tls # these appear at the same time ;)

        if updatecameras: # request also connection status
            try:
                content, headers = await self._request("/0/detection/connection")
                for match in re.finditer(r"\s*(\d+).*(OK|Lost).*\n", content):
                    camera_id = int(match.group(1))
                    value = match.group(2)
                    self.getcamera(camera_id)._connected = (value == "OK")
            except Exception as exception:
                pass

        return


    async def config_list(self, id) -> Dict[str, Any]:
        config = {}
        content, headers = await self._request(f"/{id}/config/list")
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

    async def config_set(self, param: str, value: Any, force: bool = False, id: int = 0):

        config = self._configs.get(id)
        if (force is False) and config and (config.get(param) == value):
            return

        await self._request(f"/{id}/config/set?{param}={value}")

        if config:
            config[param] = value

        return

    async def _request(self, api_url, method: str = 'GET', timeout=DEFAULT_TIMEOUT) -> str:
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
                    response = await self._session.request(
                        method,
                        urljoin(self._server_url, api_url),
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


    @staticmethod
    def generate_url(host, port, proto = "http") -> str:
        return f"{proto}://{host}:{port}"


class MotionCamera:

    def __init__(self, client: MotionHttpClient, id: int):
        self._client : MotionHttpClient = client
        self._id: int = id
        self._camera_id: int = self.config.get("camera_id", id) # cache here since we're using it a lot
        self._connected = False


    def __getattr__(self, attr):
        return self.config[attr]


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
        to the motion thread_id when not explicitly comfigured
        """
        return self._camera_id


    @property
    def connected(self) -> bool:
        return self._connected


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


    @property
    def name(self) -> str:
        return self.config.get("camera_name", self._id)


