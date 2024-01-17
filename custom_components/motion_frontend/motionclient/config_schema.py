"""
Motion daemon config parameters definitions
"""
from __future__ import annotations

from collections import ChainMap
import typing
from typing import Any, Container

import voluptuous as vol

GLOBAL_ID = "0"  # url/key for global motion.conf and actions

# miscellaneus values for boolean or enum param types
NULL_SET = {"(not defined)", "(null)"}
VALUE_ON = "on"
VALUE_OFF = "off"
BOOL_SET = {VALUE_ON, VALUE_OFF}
VALUE_FORCE = "force"
VALUE_NONE = "none"
VALUE_V = "v"
VALUE_H = "h"
VALUE_PREVIEW = "preview"
VALUE_BOX = "box"
VALUE_REDBOX = "redbox"
VALUE_CROSS = "cross"
VALUE_REDCROSS = "redcross"
VALUE_FIRST = "first"
VALUE_BEST = "best"
VALUE_COR = "COR"
VALUE_STR = "STR"
VALUE_ENC = "ENC"
VALUE_NET = "NET"
VALUE_DBL = "DBL"
VALUE_EVT = "EVT"
VALUE_TRK = "TRK"
VALUE_VID = "VID"
VALUE_ALL = "ALL"
LOG_TYPE_SET = {
    VALUE_COR,
    VALUE_STR,
    VALUE_ENC,
    VALUE_NET,
    VALUE_DBL,
    VALUE_EVT,
    VALUE_TRK,
    VALUE_VID,
    VALUE_ALL,
}
MOVIE_CODEC_SET = {
    "mpeg4",
    "msmpeg4",
    "swf",
    "flv",
    "ffv1",
    "mov",
    "mp4",
    "mkv",
    "hevc",
}
TIMELAPSE_MODE_SET = {
    "hourly",
    "daily",
    "weekly-sunday",
    "weekly-monday",
    "monthly",
    "manual",
}
TIMELAPSE_CODEC_SET = {"mpg", "mpeg4"}
PICTURE_TYPE_SET = {"jpeg", "webp", "ppm"}

AUTH_MODE_NONE = 0
AUTH_MODE_BASIC = 1
AUTH_MODE_DIGEST = 2
AUTH_MODE_SET = {AUTH_MODE_NONE, AUTH_MODE_BASIC, AUTH_MODE_DIGEST}


#
# VALIDATORS
#
def validate_userpass(value):
    if value is None:
        return value

    if ":" in value:
        return value

    raise vol.ValueInvalid("Missing ':' separator (username:password)")


#
# TYPED MOTION PARAMETERS
#
class Param(str):
    """
    base class for parameter values
    exposes parameter descriptor and validator
    """

    descriptor: "Descriptor"

    def __new__(cls, value: str, descriptor: "Descriptor"):
        _self = str.__new__(cls, value)
        _self.descriptor = descriptor
        return _self

    @property
    def validator(self):
        return self.descriptor.validator


class UpperStringParam(Param):
    """
    represent motion enumerations (uppercase enums)
    """

    def __new__(cls, value: str, descriptor: "Descriptor"):
        return super().__new__(cls, value.upper(), descriptor)

    def __eq__(self, x: object) -> bool:
        return super().__eq__(x.upper() if isinstance(x, str) else x)


class IntParam(int):
    descriptor: "Descriptor"
    _str: str

    def __new__(cls, value, descriptor: "Descriptor"):
        _self = int.__new__(cls, value)
        _self.descriptor = descriptor
        _self._str = str(value)
        return _self

    def __eq__(self, x: object) -> bool:
        if isinstance(x, str):
            return self._str == x
        return super().__eq__(x)

    def __str__(self) -> str:
        return self._str

    @property
    def validator(self):
        return self.descriptor.validator


class BoolParam(Param):
    boolvalue: bool

    def __new__(cls, value: str | bool, descriptor: "Descriptor"):
        isstr = isinstance(value, str)
        boolvalue = (value == VALUE_ON) if isstr else bool(value)
        _self = super().__new__(
            cls, value if isstr else VALUE_ON if boolvalue else VALUE_OFF, descriptor
        )
        _self.boolvalue = boolvalue
        return _self

    def __eq__(self, x: object) -> bool:
        if isinstance(x, bool):
            return self.boolvalue == x
        return super().__eq__(x)

    def __bool__(self) -> bool:
        return self.boolvalue


AnyParam: typing.TypeAlias = Param | UpperStringParam | IntParam | BoolParam | None

#
# static 'descriptors' helper class to describe motion params properties
#
class Descriptor:
    def __init__(
        self,
        _builder: type[Param] | type[IntParam],
        _validator: Any = None,
        _set: Container | None = None,
    ):
        self.builder = _builder
        self.set = _set
        self.validator = _validator or (vol.In(_set) if _set else str)


DESCRIPTOR_STR = Descriptor(Param, _validator=str)
DESCRIPTOR_BOOL = Descriptor(BoolParam, _set=BOOL_SET)
DESCRIPTOR_INT = Descriptor(IntParam, _validator=int)


def DESCRIPTOR_INT_RANGE(min: int | None = None, max: int | None = None) -> Descriptor:
    return Descriptor(IntParam, _validator=vol.Range(min=min, max=max))


def DESCRIPTOR_INT_ENUM(_set: Container) -> Descriptor:
    return Descriptor(IntParam, _set=_set)


DESCRIPTOR_INT_POSITIVE = DESCRIPTOR_INT_RANGE(min=0)
DESCRIPTOR_INT_PERCENT = DESCRIPTOR_INT_RANGE(min=0, max=100)
DESCRIPTOR_BYTE = DESCRIPTOR_INT_RANGE(min=0, max=255)


def DESCRIPTOR_STRING_ENUM(_set: Container) -> Descriptor:
    return Descriptor(Param, _set=_set)


def DESCRIPTOR_UPPERSTRING_ENUM(_set: Container) -> Descriptor:
    return Descriptor(UpperStringParam, _set=_set)


def build_value(key: str, value: Any):
    """
    Polimorfic factory for typed params:
    key specifies a well-defined type usually so we parse and cast value
    accordingly.
    return None (untyped then) if value represent a None
    Fallback to plain 'str' if anything goes wrong
    """

    if value in NULL_SET:
        return None

    if (value in BOOL_SET) or isinstance(value, bool):
        return BoolParam(value, DESCRIPTOR_BOOL)

    desc = SCHEMA.get(key)

    if isinstance(value, int) or str(value).lstrip("-").isnumeric():
        return IntParam(value, desc or DESCRIPTOR_INT)

    if desc:
        return desc.builder(value, desc)

    return Param(value, DESCRIPTOR_STR)


#
# List (almost exhaustive) of motion params and corresponding descriptors
#
# SYSTEM PROCESSING
SECTION_SYSTEM = "system"
#
SETUP_MODE = "setup_mode"
TARGET_DIR = "target_dir"
LOG_FILE = "log_file"
LOGFILE = "logfile"  # -> 4.1.1 log_file
LOG_LEVEL = "log_level"
LOG_TYPE = "log_type"
QUIET = "quiet"
NATIVE_LANGUAGE = "native_language"
CAMERA_NAME = "camera_name"
CAMERA_ID = "camera_id"
SECTION_SYSTEM_MAP = {
    SETUP_MODE: DESCRIPTOR_BOOL,
    TARGET_DIR: DESCRIPTOR_STR,
    LOG_FILE: DESCRIPTOR_STR,
    LOG_LEVEL: DESCRIPTOR_INT_RANGE(min=1, max=9),
    LOG_TYPE: DESCRIPTOR_UPPERSTRING_ENUM(LOG_TYPE_SET),
    QUIET: DESCRIPTOR_BOOL,
    NATIVE_LANGUAGE: DESCRIPTOR_BOOL,
    CAMERA_NAME: DESCRIPTOR_STR,
    CAMERA_ID: DESCRIPTOR_INT_POSITIVE,
    LOGFILE: DESCRIPTOR_STR,  # deprecated
}
# V4L2 CAMERAS
SECTION_V4L2 = "v4l2"
#
VIDEO_DEVICE = "video_device"
VIDEODEVICE = "videodevice"  # deprecated
VIDEO_PARAMS = "video_params"
VID_CONTROL_PARAMS = "vid_control_params"  # deprecated
V4L2_PALETTE = "v4l2_palette"
BRIGHTNESS = "brightness"  # deprecated
CONTRAST = "contrast"  # deprecated
HUE = "hue"  # deprecated
POWER_LINE_FREQUENCY = "power_line_frequency"  # deprecated
SATURATION = "saturation"  # deprecated
AUTO_BRIGHTNESS = "auto_brightness"
TUNER_DEVICE = "tuner_device"
TUNERDEVICE = "tunerdevice"  # deprecated
SECTION_V4L2_MAP = {
    VIDEO_DEVICE: DESCRIPTOR_STR,
    VIDEODEVICE: DESCRIPTOR_STR,  # deprecated
    VIDEO_PARAMS: DESCRIPTOR_STR,
    VID_CONTROL_PARAMS: DESCRIPTOR_STR,  # deprecated
    V4L2_PALETTE: DESCRIPTOR_INT_RANGE(min=0, max=21),
    BRIGHTNESS: DESCRIPTOR_BYTE,  # deprecated
    CONTRAST: DESCRIPTOR_BYTE,  # deprecated
    HUE: DESCRIPTOR_BYTE,  # deprecated
    POWER_LINE_FREQUENCY: DESCRIPTOR_INT_RANGE(min=-1, max=3),
    SATURATION: DESCRIPTOR_BYTE,  # deprecated
    AUTO_BRIGHTNESS: DESCRIPTOR_INT_RANGE(min=0, max=3),
    TUNER_DEVICE: DESCRIPTOR_STR,
    TUNERDEVICE: DESCRIPTOR_STR,  # deprecated
}
# NETWORK CAMERAS
SECTION_NETCAM = "netcam"
#
NETCAM_URL = "netcam_url"
NETCAM_HIGHRES = "netcam_highres"
NETCAM_USERPASS = "netcam_userpass"
NETCAM_DECODER = "netcam_decoder"
NETCAM_KEEPALIVE = "netcam_keepalive"
NETCAM_USE_TCP = "netcam_use_tcp"
SECTION_NETCAM_MAP = {
    NETCAM_URL: DESCRIPTOR_STR,
    NETCAM_HIGHRES: DESCRIPTOR_STR,
    NETCAM_DECODER: DESCRIPTOR_STR,
    NETCAM_USERPASS: DESCRIPTOR_STR,  # Descriptor(str, _validator=validate_userpass),
    NETCAM_USE_TCP: DESCRIPTOR_STRING_ENUM((VALUE_ON, VALUE_OFF, VALUE_FORCE)),
    NETCAM_KEEPALIVE: DESCRIPTOR_BOOL,
}
# RASPI CAMERA
SECTION_MMALCAM = "mmalcam"
#
MMALCAM_NAME = "mmalcam_name"
MMALCAM_CONTROL_PARAMS = "mmalcam_control_params"
SECTION_MMALCAM_MAP = {
    MMALCAM_NAME: DESCRIPTOR_STR,
    MMALCAM_CONTROL_PARAMS: DESCRIPTOR_STR,
}
#
SECTION_WEBCONTROL = "webcontrol"
#
WEBCONTROL_TLS = "webcontrol_tls"
SECTION_WEBCONTROL_MAP = {WEBCONTROL_TLS: DESCRIPTOR_BOOL}
#
SECTION_STREAM = "stream"
#
STREAM_PORT = "stream_port"
STREAM_AUTH_METHOD = "stream_auth_method"
STREAM_AUTHENTICATION = "stream_authentication"
STREAM_TLS = "stream_tls"
STREAM_GREY = "stream_grey"
STREAM_MAXRATE = "stream_maxrate"
STREAM_MOTION = "stream_motion"
STREAM_QUALITY = "stream_quality"
STREAM_PREVIEW_METHOD = "stream_preview_method"
SECTION_STREAM_MAP = {
    STREAM_PORT: DESCRIPTOR_INT_POSITIVE,
    STREAM_AUTH_METHOD: DESCRIPTOR_INT_ENUM(AUTH_MODE_SET),
    STREAM_AUTHENTICATION: DESCRIPTOR_STR,
    STREAM_TLS: DESCRIPTOR_BOOL,
    STREAM_GREY: DESCRIPTOR_BOOL,
    STREAM_MAXRATE: DESCRIPTOR_INT_POSITIVE,
    STREAM_MOTION: DESCRIPTOR_BOOL,
    STREAM_QUALITY: DESCRIPTOR_INT_RANGE(min=1, max=100),
    STREAM_PREVIEW_METHOD: DESCRIPTOR_INT_ENUM((0, 1, 2, 3, 4)),
}
# IMAGE PROCESSING
SECTION_IMAGE = "image"
#
WIDTH = "width"
HEIGHT = "height"
FRAMERATE = "framerate"
MINIMUM_FRAME_TIME = "minimum_frame_time"
ROTATE = "rotate"
FLIP_AXIS = "flip_axis"
LOCATE_MOTION_MODE = "locate_motion_mode"
LOCATE_MOTION_STYLE = "locate_motion_style"
TEXT_LEFT = "text_left"
TEXT_RIGHT = "text_right"
TEXT_CHANGES = "text_changes"
TEXT_SCALE = "text_scale"
TEXT_EVENT = "text_event"
SECTION_IMAGE_MAP = {
    WIDTH: DESCRIPTOR_INT_POSITIVE,
    HEIGHT: DESCRIPTOR_INT_POSITIVE,
    FRAMERATE: DESCRIPTOR_INT_RANGE(min=2, max=100),
    MINIMUM_FRAME_TIME: DESCRIPTOR_INT_POSITIVE,
    ROTATE: DESCRIPTOR_INT_ENUM((0, 90, 180, 270)),
    FLIP_AXIS: DESCRIPTOR_STRING_ENUM((VALUE_NONE, VALUE_V, VALUE_H)),
    LOCATE_MOTION_MODE: DESCRIPTOR_STRING_ENUM((VALUE_OFF, VALUE_ON, VALUE_PREVIEW)),
    LOCATE_MOTION_STYLE: DESCRIPTOR_STRING_ENUM(
        (VALUE_BOX, VALUE_REDBOX, VALUE_CROSS, VALUE_REDCROSS)
    ),
    TEXT_LEFT: DESCRIPTOR_STR,
    TEXT_RIGHT: DESCRIPTOR_STR,
    TEXT_CHANGES: DESCRIPTOR_BOOL,
    TEXT_SCALE: DESCRIPTOR_INT_RANGE(min=1, max=10),
    TEXT_EVENT: DESCRIPTOR_STR,
}
#
SECTION_MOTION = "motion"
#
EMULATE_MOTION = "emulate_motion"
THRESHOLD = "threshold"
THRESHOLD_MAXIMUM = "threshold_maximum"
THRESHOLD_TUNE = "threshold_tune"
NOISE_LEVEL = "noise_level"
NOISE_TUNE = "noise_tune"
DESPECKLE_FILTER = "despeckle_filter"
AREA_DETECT = "area_detect"
MASK_FILE = "mask_file"
MASK_PRIVACY = "mask_privacy"
SMART_MASK_SPEED = "smart_mask_speed"
LIGHTSWITCH_PERCENT = "lightswitch_percent"
LIGHTSWITCH = "lightswitch"  # -> 4.1.1
LIGHTSWITCH_FRAMES = "lightswitch_frames"
MINIMUM_MOTION_FRAMES = "minimum_motion_frames"
EVENT_GAP = "event_gap"
PRE_CAPTURE = "pre_capture"
POST_CAPTURE = "post_capture"
SECTION_MOTION_MAP = {
    EMULATE_MOTION: DESCRIPTOR_BOOL,
    THRESHOLD: DESCRIPTOR_INT_RANGE(min=1),
    THRESHOLD_MAXIMUM: DESCRIPTOR_INT_POSITIVE,
    THRESHOLD_TUNE: DESCRIPTOR_BOOL,
    NOISE_LEVEL: DESCRIPTOR_INT_RANGE(min=1, max=255),
    NOISE_TUNE: DESCRIPTOR_BOOL,
    DESPECKLE_FILTER: DESCRIPTOR_STR,
    AREA_DETECT: DESCRIPTOR_STR,
    MASK_FILE: DESCRIPTOR_STR,
    MASK_PRIVACY: DESCRIPTOR_STR,
    SMART_MASK_SPEED: DESCRIPTOR_INT_RANGE(min=0, max=10),
    LIGHTSWITCH_PERCENT: DESCRIPTOR_INT_PERCENT,
    LIGHTSWITCH: DESCRIPTOR_INT_PERCENT,
    LIGHTSWITCH_FRAMES: DESCRIPTOR_INT_RANGE(min=1, max=1000),
    MINIMUM_MOTION_FRAMES: DESCRIPTOR_INT_RANGE(min=1, max=1000),
    EVENT_GAP: DESCRIPTOR_INT_POSITIVE,
    PRE_CAPTURE: DESCRIPTOR_INT_RANGE(min=0, max=100),
    POST_CAPTURE: DESCRIPTOR_INT_POSITIVE,
}
#
SECTION_SCRIPT = "script"
#
ON_EVENT_START = "on_event_start"
ON_EVENT_END = "on_event_end"
ON_PICTURE_SAVE = "on_picture_save"
ON_MOTION_DETECTED = "on_motion_detected"
ON_AREA_DETECTED = "on_area_detected"
ON_MOVIE_START = "on_movie_start"
ON_MOVIE_END = "on_movie_end"
ON_CAMERA_LOST = "on_camera_lost"
ON_CAMERA_FOUND = "on_camera_found"
SECTION_SCRIPT_MAP = {
    ON_EVENT_START: DESCRIPTOR_STR,
    ON_EVENT_END: DESCRIPTOR_STR,
    ON_PICTURE_SAVE: DESCRIPTOR_STR,
    ON_MOTION_DETECTED: DESCRIPTOR_STR,
    ON_AREA_DETECTED: DESCRIPTOR_STR,
    ON_MOVIE_START: DESCRIPTOR_STR,
    ON_MOVIE_END: DESCRIPTOR_STR,
    ON_CAMERA_LOST: DESCRIPTOR_STR,
    ON_CAMERA_FOUND: DESCRIPTOR_STR,
}
#
SECTION_PICTURE = "picture"
#
PICTURE_OUTPUT = "picture_output"
OUTPUT_PICTURES = "output_pictures"  # -> 4.1.1
PICTURE_OUTPUT_MOTION = "picture_output_motion"
OUTPUT_DEBUG_PICTURES = "output_debug_pictures"  # -> 4.1.1
PICTURE_TYPE = "picture_type"
PICTURE_QUALITY = "picture_quality"
QUALITY = "quality"  # -> 4.1.1
PICTURE_EXIF = "picture_exif"
EXIF_TEXT = "exif_text"  # -> 4.1.1
PICTURE_FILENAME = "picture_filename"
SNAPSHOT_INTERVAL = "snapshot_interval"
SNAPSHOT_FILENAME = "snapshot_filename"
SECTION_PICTURE_MAP = {
    PICTURE_OUTPUT: DESCRIPTOR_STRING_ENUM(
        (VALUE_OFF, VALUE_ON, VALUE_FIRST, VALUE_BEST)
    ),
    PICTURE_OUTPUT_MOTION: DESCRIPTOR_BOOL,
    PICTURE_TYPE: DESCRIPTOR_STRING_ENUM(PICTURE_TYPE_SET),
    PICTURE_QUALITY: DESCRIPTOR_INT_PERCENT,
    PICTURE_EXIF: DESCRIPTOR_STR,
    PICTURE_FILENAME: DESCRIPTOR_STR,
    SNAPSHOT_INTERVAL: DESCRIPTOR_INT_POSITIVE,
    SNAPSHOT_FILENAME: DESCRIPTOR_STR,
    OUTPUT_PICTURES: DESCRIPTOR_STRING_ENUM(
        (VALUE_OFF, VALUE_ON, VALUE_FIRST, VALUE_BEST)
    ),
    OUTPUT_DEBUG_PICTURES: DESCRIPTOR_BOOL,
    QUALITY: DESCRIPTOR_INT_PERCENT,
    EXIF_TEXT: DESCRIPTOR_STR,
}
#
SECTION_MOVIE = "movie"
#
MOVIE_OUTPUT = "movie_output"
MOVIE_OUTPUT_MOTION = "movie_output_motion"
MOVIE_MAX_TIME = "movie_max_time"
MOVIE_BPS = "movie_bps"
MOVIE_QUALITY = "movie_quality"
MOVIE_CODEC = "movie_codec"
MOVIE_DUPLICATE_FRAMES = "movie_duplicate_frames"
MOVIE_PASSTHROUGH = "movie_passthrough"
MOVIE_FILENAME = "movie_filename"
MOVIE_EXTPIPE_USE = "movie_extpipe_use"
MOVIE_EXTPIPE = "movie_extpipe"
# deprecated
FFMPEG_OUTPUT_MOVIES = "ffmpeg_output_movies"  # -> 4.1.1 movie_output
FFMPEG_OUTPUT_DEBUG_MOVIES = (
    "ffmpeg_output_debug_movies"  # -> 4.1.1 movie_output_motion
)
MAX_MOVIE_TIME = "max_movie_time"  # -> 4.1.1 movie_max_time
FFMPEG_BPS = "ffmpeg_bps"  # -> 4.1.1 movie_bps
FFMPEG_VARIABLE_BITRATE = "ffmpeg_variable_bitrate"  # -> 4.1.1 movie_quality
FFMPEG_VIDEO_CODEC = "ffmpeg_video_codec"  # -> 4.1.1 movie_codec
FFMPEG_DUPLICATE_FRAMES = "ffmpeg_duplicate_frames"  # -> 4.1.1 movie_duplicate_frames
USE_EXTPIPE = "use_extpipe"  # -> 4.1.1 movie_extpipe_use
EXTPIPE = "extpipe"  # -> 4.1.1 movie_extpipe
SECTION_MOVIE_MAP = {
    MOVIE_OUTPUT: DESCRIPTOR_BOOL,
    MOVIE_OUTPUT_MOTION: DESCRIPTOR_BOOL,
    MOVIE_MAX_TIME: DESCRIPTOR_INT_POSITIVE,
    MOVIE_BPS: DESCRIPTOR_INT_POSITIVE,
    MOVIE_QUALITY: DESCRIPTOR_INT_PERCENT,
    MOVIE_CODEC: DESCRIPTOR_STRING_ENUM(MOVIE_CODEC_SET),
    MOVIE_DUPLICATE_FRAMES: DESCRIPTOR_BOOL,
    MOVIE_PASSTHROUGH: DESCRIPTOR_BOOL,
    MOVIE_FILENAME: DESCRIPTOR_STR,
    MOVIE_EXTPIPE_USE: DESCRIPTOR_BOOL,
    MOVIE_EXTPIPE: DESCRIPTOR_STR,
    FFMPEG_OUTPUT_MOVIES: DESCRIPTOR_BOOL,
    FFMPEG_OUTPUT_DEBUG_MOVIES: DESCRIPTOR_BOOL,
    MAX_MOVIE_TIME: DESCRIPTOR_INT_POSITIVE,
    FFMPEG_BPS: DESCRIPTOR_INT_POSITIVE,
    FFMPEG_VARIABLE_BITRATE: DESCRIPTOR_INT_PERCENT,
    FFMPEG_VIDEO_CODEC: DESCRIPTOR_STRING_ENUM(MOVIE_CODEC_SET),
    FFMPEG_DUPLICATE_FRAMES: DESCRIPTOR_BOOL,
    USE_EXTPIPE: DESCRIPTOR_BOOL,
    EXTPIPE: DESCRIPTOR_STR,
}
#
SECTION_TIMELAPSE = "timelapse"
#
TIMELAPSE_INTERVAL = "timelapse_interval"
TIMELAPSE_MODE = "timelapse_mode"
TIMELAPSE_FPS = "timelapse_fps"
TIMELAPSE_CODEC = "timelapse_codec"
TIMELAPSE_FILENAME = "timelapse_filename"
SECTION_TIMELAPSE_MAP = {
    TIMELAPSE_INTERVAL: DESCRIPTOR_INT_POSITIVE,
    TIMELAPSE_MODE: DESCRIPTOR_STRING_ENUM(TIMELAPSE_MODE_SET),
    TIMELAPSE_FPS: DESCRIPTOR_INT_RANGE(min=0, max=100),
    TIMELAPSE_CODEC: DESCRIPTOR_STRING_ENUM(TIMELAPSE_CODEC_SET),
    TIMELAPSE_FILENAME: DESCRIPTOR_STR,
}
#
SECTION_DATABASE = "database"
#
DATABASE_TYPE = "database_type"
DATABASE_DBNAME = "database_dbname"
DATABASE_HOST = "database_host"
DATABASE_PORT = "database_port"
DATABASE_USER = "database_user"
DATABASE_PASSWORD = "database_password"
DATABASE_BUSY_TIMEOUT = "database_busy_timeout"
SQL_LOG_PICTURE = "sql_log_picture"
SQL_LOG_SNAPSHOT = "sql_log_snapshot"
SQL_LOG_MOVIE = "sql_log_movie"
SQL_LOG_TIMELAPSE = "sql_log_timelapse"
SQL_QUERY = "sql_query"
SQL_QUERY_START = "sql_query_start"
SQL_QUERY_STOP = "sql_query_stop"
SECTION_DATABASE_MAP = {
    DATABASE_TYPE: DESCRIPTOR_STR,
    DATABASE_DBNAME: DESCRIPTOR_STR,
    DATABASE_HOST: DESCRIPTOR_STR,
    DATABASE_PORT: DESCRIPTOR_INT_POSITIVE,
    DATABASE_USER: DESCRIPTOR_STR,
    DATABASE_PASSWORD: DESCRIPTOR_STR,
    DATABASE_BUSY_TIMEOUT: DESCRIPTOR_INT_POSITIVE,
    SQL_LOG_PICTURE: DESCRIPTOR_BOOL,
    SQL_LOG_SNAPSHOT: DESCRIPTOR_BOOL,
    SQL_LOG_MOVIE: DESCRIPTOR_BOOL,
    SQL_LOG_TIMELAPSE: DESCRIPTOR_BOOL,
    SQL_QUERY: DESCRIPTOR_STR,
    SQL_QUERY_START: DESCRIPTOR_STR,
    SQL_QUERY_STOP: DESCRIPTOR_STR,
}
#
SECTION_TRACK = "track"
#
TRACK_TYPE = "track_type"
TRACK_AUTO = "track_auto"
TRACK_PORT = "track_port"
TRACK_MOTORX = "track_motorx"
TRACK_MOTORX_REVERSE = "track_motorx_reverse"
TRACK_MOTORY = "track_motory"
TRACK_MOTORY_REVERSE = "track_motory_reverse"
TRACK_MAXX = "track_maxx"
TRACK_MINX = "track_minx"
TRACK_MAXY = "track_maxy"
TRACK_MINY = "track_miny"
TRACK_HOMEX = "track_homex"
TRACK_HOMEY = "track_homey"
TRACK_IOMOJO_ID = "track_iomojo_id"
TRACK_STEP_ANGLE_X = "track_step_angle_x"
TRACK_STEP_ANGLE_Y = "track_step_angle_y"
TRACK_MOVE_WAIT = "track_move_wait"
TRACK_SPEED = "track_speed"
TRACK_STEPSIZE = "track_stepsize"
TRACK_GENERIC_MOVE = "track_generic_move"
SECTION_TRACK_MAP = {
    TRACK_TYPE: DESCRIPTOR_INT,
    TRACK_AUTO: DESCRIPTOR_BOOL,
    TRACK_PORT: DESCRIPTOR_STR,
    TRACK_MOTORX: DESCRIPTOR_INT_POSITIVE,
    TRACK_MOTORX_REVERSE: DESCRIPTOR_BOOL,
    TRACK_MOTORY: DESCRIPTOR_INT_POSITIVE,
    TRACK_MOTORY_REVERSE: DESCRIPTOR_BOOL,
    TRACK_MAXX: DESCRIPTOR_INT_POSITIVE,
    TRACK_MINX: DESCRIPTOR_INT_POSITIVE,
    TRACK_MAXY: DESCRIPTOR_INT_POSITIVE,
    TRACK_MINY: DESCRIPTOR_INT_POSITIVE,
    TRACK_HOMEX: DESCRIPTOR_INT_POSITIVE,
    TRACK_HOMEY: DESCRIPTOR_INT_POSITIVE,
    TRACK_IOMOJO_ID: DESCRIPTOR_INT_POSITIVE,
    TRACK_STEP_ANGLE_X: DESCRIPTOR_INT_POSITIVE,
    TRACK_STEP_ANGLE_Y: DESCRIPTOR_INT_POSITIVE,
    TRACK_MOVE_WAIT: DESCRIPTOR_INT_POSITIVE,
    TRACK_SPEED: DESCRIPTOR_INT_POSITIVE,
    TRACK_STEPSIZE: DESCRIPTOR_INT_POSITIVE,
    TRACK_GENERIC_MOVE: DESCRIPTOR_STR,
}

SECTION_SET_MAP: typing.MutableMapping[str, dict[str, Descriptor]] = {
    SECTION_SYSTEM: SECTION_SYSTEM_MAP,
    SECTION_V4L2: SECTION_V4L2_MAP,
    SECTION_NETCAM: SECTION_NETCAM_MAP,
    SECTION_MMALCAM: SECTION_MMALCAM_MAP,
    SECTION_WEBCONTROL: SECTION_WEBCONTROL_MAP,
    SECTION_STREAM: SECTION_STREAM_MAP,
    SECTION_IMAGE: SECTION_IMAGE_MAP,
    SECTION_MOTION: SECTION_MOTION_MAP,
    SECTION_SCRIPT: SECTION_SCRIPT_MAP,
    SECTION_PICTURE: SECTION_PICTURE_MAP,
    SECTION_MOVIE: SECTION_MOVIE_MAP,
    SECTION_TIMELAPSE: SECTION_TIMELAPSE_MAP,
    SECTION_DATABASE: SECTION_DATABASE_MAP,
    SECTION_TRACK: SECTION_TRACK_MAP,
}

"""
    config options generally have meaning both for global motion.conf
    working as a 'default' for every camera like 'threshold' or 'framerate'
    Some are only meaningful at the camera level:
    i.e. a default is meaningless ('netcam_url')
    Some are only valid at the global level (see motion daemon implementation)
"""
# list options which should be available and meaningful only at the camera config level
CAMERACONFIG_SET = {
    CAMERA_ID,
    CAMERA_NAME,
    VIDEO_DEVICE,
    VIDEODEVICE,
    NETCAM_URL,
    NETCAM_HIGHRES,
    MMALCAM_NAME,
    MMALCAM_CONTROL_PARAMS,
}
# list options which are valid and meaningful only at the global motion.conf
GLOBALCONFIG_SET = {
    LOG_FILE,
    LOG_LEVEL,
    LOG_TYPE,
    LOGFILE,
    NATIVE_LANGUAGE,
    WEBCONTROL_TLS,
    STREAM_AUTHENTICATION,
}

# list options which requires a thread restart to be in place
RESTARTCONFIG_SET = {
    WIDTH,
    HEIGHT,
    ROTATE,
    FLIP_AXIS,
    VIDEO_DEVICE,
    VIDEODEVICE,
    NETCAM_URL,
    MMALCAM_NAME,
    MMALCAM_CONTROL_PARAMS,
}

SCHEMA: typing.MutableMapping[str, Descriptor] = ChainMap(
    SECTION_SYSTEM_MAP,
    SECTION_V4L2_MAP,
    SECTION_NETCAM_MAP,
    SECTION_MMALCAM_MAP,
    SECTION_WEBCONTROL_MAP,
    SECTION_STREAM_MAP,
    SECTION_IMAGE_MAP,
    SECTION_MOTION_MAP,
    SECTION_SCRIPT_MAP,
    SECTION_PICTURE_MAP,
    SECTION_MOVIE_MAP,
    SECTION_TIMELAPSE_MAP,
    SECTION_DATABASE_MAP,
    SECTION_TRACK_MAP,
)
