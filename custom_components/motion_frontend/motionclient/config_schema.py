"""
Motion daemon config parameters definitions
"""
from typing import Any, Dict
import voluptuous as vol


GLOBAL_ID = '0' # url/key for global motion.conf and actions

# miscellaneus values for boolean or enum param types
NULL_SET = ("(not defined)", "(null)")
VALUE_ON = 'on'
VALUE_OFF = 'off'
BOOL_SET = (VALUE_ON, VALUE_OFF)
VALUE_FORCE = 'force'
VALUE_NONE = 'none'
VALUE_V = 'v'
VALUE_H = 'h'
VALUE_PREVIEW = 'preview'
VALUE_BOX = 'box'
VALUE_REDBOX = 'redbox'
VALUE_CROSS = 'cross'
VALUE_REDCROSS = 'redcross'
VALUE_FIRST = 'first'
VALUE_BEST = 'best'
VALUE_COR = 'COR'
VALUE_STR = 'STR'
VALUE_ENC = 'ENC'
VALUE_NET = 'NET'
VALUE_DBL = 'DBL'
VALUE_EVT = 'EVT'
VALUE_TRK = 'TRK'
VALUE_VID = 'VID'
VALUE_ALL = 'ALL'
LOG_TYPE_SET = (
    VALUE_COR, VALUE_STR, VALUE_ENC, VALUE_NET,
    VALUE_DBL, VALUE_EVT, VALUE_TRK, VALUE_VID, VALUE_ALL)
MOVIE_CODEC_SET = (
    'mpeg4', 'msmpeg4', 'swf', 'flv', 'ffv1', 'mov', 'mp4', 'mkv', 'hevc'
)
TIMELAPSE_MODE_SET = (
    'hourly', 'daily', 'weekly-sunday', 'weekly-monday', 'monthly', 'manual'
)
TIMELAPSE_CODEC_SET = (
    'mpg', 'mpeg4'
)
PICTURE_TYPE_SET = ( "jpeg", "webp", "ppm")

AUTH_MODE_NONE = 0
AUTH_MODE_BASIC = 1
AUTH_MODE_DIGEST = 2
AUTH_MODE_SET = (AUTH_MODE_NONE, AUTH_MODE_BASIC, AUTH_MODE_DIGEST)

# SYSTEM PROCESSING
SECTION_SYSTEM = "system"
#
SETUP_MODE = 'setup_mode'
CAMERA_ID = 'camera_id'
CAMERA_NAME = 'camera_name'
TARGET_DIR = 'target_dir'
LOG_FILE = 'log_file'
LOGFILE = 'logfile' # -> 4.1.1 log_file
LOG_LEVEL = 'log_level'
LOG_TYPE = 'log_type'
SECTION_SYSTEM_SET = (
    SETUP_MODE,
    CAMERA_ID, CAMERA_NAME,
    TARGET_DIR,
    LOG_FILE, LOG_LEVEL, LOG_TYPE,
    LOGFILE
)
# NETWORK CAMERAS
SECTION_NETCAM = "netcam"
#
NETCAM_URL = 'netcam_url'
NETCAM_HIGHRES = 'netcam_highres'
NETCAM_USERPASS = 'netcam_userpass'
NETCAM_DECODER = 'netcam_decoder'
NETCAM_KEEPALIVE = 'netcam_keepalive'
NETCAM_USE_TCP = 'netcam_use_tcp'
SECTION_NETCAM_SET = (
    NETCAM_URL, NETCAM_HIGHRES,
    NETCAM_USERPASS,
    NETCAM_DECODER,
    NETCAM_KEEPALIVE,
    NETCAM_USE_TCP,
)
# WEBCONTROL
SECTION_WEBCONTROL = 'webcontrol'
WEBCONTROL_TLS = 'webcontrol_tls'
SECTION_WEBCONTROL_SET = (
    WEBCONTROL_TLS,
)
# STREAMING
SECTION_STREAM = "stream"
#
STREAM_PORT = 'stream_port'
STREAM_AUTH_METHOD = 'stream_auth_method'
STREAM_AUTHENTICATION = 'stream_authentication'
STREAM_TLS = 'stream_tls'
STREAM_GREY = 'stream_grey'
STREAM_MAXRATE = 'stream_maxrate'
STREAM_MOTION = 'stream_motion'
STREAM_QUALITY = 'stream_quality'
STREAM_PREVIEW_METHOD = 'stream_preview_method'
SECTION_STREAM_SET = (
    STREAM_PORT,
    STREAM_AUTH_METHOD, STREAM_AUTHENTICATION,
    STREAM_TLS,
    STREAM_GREY,
    STREAM_MAXRATE,
    STREAM_MOTION,
    STREAM_QUALITY,
    STREAM_PREVIEW_METHOD
)
# IMAGE PROCESSING
SECTION_IMAGE = "image"
#
WIDTH = 'width'
HEIGHT = 'height'
FRAMERATE = 'framerate'
MINIMUM_FRAME_TIME = 'minimum_frame_time'
ROTATE = 'rotate'
FLIP_AXIS = 'flip_axis'
LOCATE_MOTION_MODE = 'locate_motion_mode'
LOCATE_MOTION_STYLE = 'locate_motion_style'
TEXT_LEFT = 'text_left'
TEXT_RIGHT = 'text_right'
TEXT_CHANGES = 'text_changes'
TEXT_SCALE = 'text_scale'
TEXT_EVENT = 'text_event'
SECTION_IMAGE_SET = (
    WIDTH, HEIGHT,
    FRAMERATE, MINIMUM_FRAME_TIME,
    ROTATE, FLIP_AXIS,
    LOCATE_MOTION_MODE, LOCATE_MOTION_STYLE,
    TEXT_LEFT, TEXT_RIGHT, TEXT_CHANGES,
    TEXT_SCALE, TEXT_EVENT
)
#
SECTION_MOTION = "motion"
#
EMULATE_MOTION = 'emulate_motion'
THRESHOLD = 'threshold'
THRESHOLD_MAXIMUM = 'threshold_maximum'
THRESHOLD_TUNE =	'threshold_tune'
NOISE_LEVEL = 'noise_level'
NOISE_TUNE = 'noise_tune'
DESPECKLE_FILTER = 'despeckle_filter'
AREA_DETECT = 'area_detect'
MASK_FILE = 'mask_file'
MASK_PRIVACY = 'mask_privacy'
SMART_MASK_SPEED = 'smart_mask_speed'
LIGHTSWITCH_PERCENT = 'lightswitch_percent'
LIGHTSWITCH = 'lightswitch' # -> 4.1.1
LIGHTSWITCH_FRAMES = 'lightswitch_frames'
MINIMUM_MOTION_FRAMES = 'minimum_motion_frames'
EVENT_GAP = 'event_gap'
PRE_CAPTURE = 'pre_capture'
POST_CAPTURE = 'post_capture'
SECTION_MOTION_SET = (
    EMULATE_MOTION,
    THRESHOLD, THRESHOLD_MAXIMUM, THRESHOLD_TUNE,
    NOISE_LEVEL, NOISE_TUNE,
    DESPECKLE_FILTER,
    AREA_DETECT,
    MASK_FILE, MASK_PRIVACY, SMART_MASK_SPEED,
    LIGHTSWITCH_PERCENT, LIGHTSWITCH_FRAMES,
    MINIMUM_MOTION_FRAMES,
    EVENT_GAP, PRE_CAPTURE, POST_CAPTURE
)
#
SECTION_SCRIPT = 'script'
#
ON_EVENT_START = 'on_event_start'
ON_EVENT_END = 'on_event_end'
ON_PICTURE_SAVE = 'on_picture_save'
ON_MOTION_DETECTED = 'on_motion_detected'
ON_AREA_DETECTED = 'on_area_detected'
ON_MOVIE_START = 'on_movie_start'
ON_MOVIE_END = 'on_movie_end'
ON_CAMERA_LOST = 'on_camera_lost'
ON_CAMERA_FOUND = 'on_camera_found'
SECTION_SCRIPT_SET = (
    ON_EVENT_START, ON_EVENT_END,
    ON_PICTURE_SAVE,
    ON_MOTION_DETECTED, ON_AREA_DETECTED,
    ON_MOVIE_START, ON_MOVIE_END,
    ON_CAMERA_LOST, ON_CAMERA_FOUND
)
#
SECTION_PICTURE = 'picture'
#
PICTURE_OUTPUT = 'picture_output'
OUTPUT_PICTURES = 'output_pictures' # -> 4.1.1
PICTURE_OUTPUT_MOTION = 'picture_output_motion'
OUTPUT_DEBUG_PICTURES = 'output_debug_pictures' # -> 4.1.1
PICTURE_TYPE = 'picture_type'
PICTURE_QUALITY = 'picture_quality'
QUALITY = 'quality' # -> 4.1.1
PICTURE_EXIF = 'picture_exif'
EXIF_TEXT = 'exif_text' # -> 4.1.1
PICTURE_FILENAME = 'picture_filename'
SNAPSHOT_INTERVAL = 'snapshot_interval'
SNAPSHOT_FILENAME = 'snapshot_filename'
SECTION_PICTURE_SET = (
    PICTURE_OUTPUT, PICTURE_OUTPUT_MOTION,
    PICTURE_TYPE, PICTURE_QUALITY,
    PICTURE_EXIF, PICTURE_FILENAME,
    SNAPSHOT_INTERVAL, SNAPSHOT_FILENAME,
    OUTPUT_PICTURES, OUTPUT_DEBUG_PICTURES,
    QUALITY,
    EXIF_TEXT,
)
#
SECTION_MOVIE = 'movie'
#
MOVIE_OUTPUT = 'movie_output'
MOVIE_OUTPUT_MOTION = 'movie_output_motion'
MOVIE_MAX_TIME = 'movie_max_time'
MOVIE_BPS = 'movie_bps'
MOVIE_QUALITY = 'movie_quality'
MOVIE_CODEC = 'movie_codec'
MOVIE_DUPLICATE_FRAMES = 'movie_duplicate_frames'
MOVIE_PASSTHROUGH = 'movie_passthrough'
MOVIE_FILENAME = 'movie_filename'
MOVIE_EXTPIPE_USE = 'movie_extpipe_use'
MOVIE_EXTPIPE = 'movie_extpipe'
# deprecated
FFMPEG_OUTPUT_MOVIES = 'ffmpeg_output_movies' # -> 4.1.1 movie_output
FFMPEG_OUTPUT_DEBUG_MOVIES = 'ffmpeg_output_debug_movies' # -> 4.1.1 movie_output_motion
MAX_MOVIE_TIME = 'max_movie_time' # -> 4.1.1 movie_max_time
FFMPEG_BPS = 'ffmpeg_bps' # -> 4.1.1 movie_bps
FFMPEG_VARIABLE_BITRATE = 'ffmpeg_variable_bitrate' # -> 4.1.1 movie_quality
FFMPEG_VIDEO_CODEC= 'ffmpeg_video_codec' # -> 4.1.1 movie_codec
FFMPEG_DUPLICATE_FRAMES = 'ffmpeg_duplicate_frames' # -> 4.1.1 movie_duplicate_frames
FFMPEG_PASSTHROUGH = 'ffmpeg_passthrough' # -> 4.1.1 movie_passthrough
USE_EXTPIPE = 'use_extpipe' # -> 4.1.1 movie_extpipe_use
EXTPIPE = 'extpipe' # -> 4.1.1 movie_extpipe
SECTION_MOVIE_SET = (
    MOVIE_OUTPUT, MOVIE_OUTPUT_MOTION,
    MOVIE_MAX_TIME,
    MOVIE_BPS, MOVIE_QUALITY, MOVIE_CODEC,
    MOVIE_DUPLICATE_FRAMES,
    MOVIE_PASSTHROUGH,
    MOVIE_FILENAME,
    MOVIE_EXTPIPE_USE, MOVIE_EXTPIPE,
    FFMPEG_OUTPUT_MOVIES, FFMPEG_OUTPUT_DEBUG_MOVIES,
    MAX_MOVIE_TIME,
    FFMPEG_BPS, FFMPEG_VARIABLE_BITRATE, FFMPEG_VIDEO_CODEC,
    FFMPEG_DUPLICATE_FRAMES,
    FFMPEG_PASSTHROUGH,
    USE_EXTPIPE, EXTPIPE,
)
#
SECTION_TIMELAPSE = 'timelapse'
#
TIMELAPSE_INTERVAL = 'timelapse_interval'
TIMELAPSE_MODE = 'timelapse_mode'
TIMELAPSE_FPS = 'timelapse_fps'
TIMELAPSE_CODEC = 'timelapse_codec'
TIMELAPSE_FILENAME = 'timelapse_filename'
SECTION_TIMELAPSE_SET = (
    TIMELAPSE_INTERVAL, TIMELAPSE_MODE,
    TIMELAPSE_FPS,TIMELAPSE_CODEC, TIMELAPSE_FILENAME,
)

SECTION_SET_MAP = {
    SECTION_SYSTEM: SECTION_SYSTEM_SET,
    SECTION_NETCAM: SECTION_NETCAM_SET,
    SECTION_WEBCONTROL: SECTION_WEBCONTROL_SET,
    SECTION_STREAM: SECTION_STREAM_SET,
    SECTION_IMAGE: SECTION_IMAGE_SET,
    SECTION_MOTION: SECTION_MOTION_SET,
    SECTION_SCRIPT: SECTION_SCRIPT_SET,
    SECTION_PICTURE: SECTION_PICTURE_SET,
    SECTION_MOVIE: SECTION_MOVIE_SET,
    SECTION_TIMELAPSE: SECTION_TIMELAPSE_SET
}

"""
    config options generally have meaning both for global motion.conf
    working as a 'default' for every camera like 'threshold' or 'framerate'
    Some are only meaningful at the camera level:
    i.e. a default is meaningless ('netcam_url')
    Some are only valid at the global level (see motion daemon implementation)
"""
# list options which should be available and meaningful only at the camera config level
CAMERACONFIG_SET = (
    CAMERA_ID, CAMERA_NAME,
    NETCAM_URL, NETCAM_HIGHRES
)
# list options which are valid and meaningful only at the global motion.conf
GLOBALCONFIG_SET = (
    LOG_FILE, LOG_LEVEL, LOG_TYPE, LOGFILE,
    WEBCONTROL_TLS
)

# list options which requires a thread restart to be in place
RESTARTCONFIG_SET = (
    WIDTH, HEIGHT, ROTATE, FLIP_AXIS,
    NETCAM_URL,
)

#
# VALIDATORS
#

#VALIDATE_BOOLEAN = vol.In(BOOL_SET)

#def validate_numeric(value):
#    pass

def validate_userpass(value):
    if value is None:
        return value

    if ':' in value:
        return value

    raise vol.ValueInvalid("Missing ':' separator (username:password)")


class Integer(int):
    """
    extend int to represent motion integers
    """
    _str = None

    @staticmethod
    def build(value:str):
        _self = Integer(value)
        _self._str = value
        return _self

    def __eq__(self, x: object) -> bool:
        if isinstance(x, str):
            return self._str == x
        return super().__eq__(x)


class Boolean(str):
    """
    extend str to represent motion booleans
    """
    _bool = None

    @staticmethod
    def build(value:str):
        _self = Boolean(value)
        _self._bool = (value == VALUE_ON)
        return _self

    def __eq__(self, x: object) -> bool:
        if isinstance(x, bool):
            return self._bool == x
        return super().__eq__(x)

    def __bool__(self) -> bool:
        return self._bool


class UpperString(str):
    """
    extend str to represent motion enumerations (uppercase enums)
    """
    @staticmethod
    def build(value:str):
        return UpperString(value.upper())

    def __eq__(self, x: object) -> bool:
        return super().__eq__(x.upper() if isinstance(x, str) else x)


class Descriptor:

    def __init__(self, _builder: Any, _validator: Any = None, _set: frozenset = None):
        self.builder = _builder
        self.set = _set
        self.validator = _validator or (vol.In(_set) if _set else None)

    @staticmethod
    def buildint(min: int = None, max: int = None) -> 'Descriptor':
        return Descriptor(Integer.build, _validator=vol.Range(min=min, max=max))

    @staticmethod
    def buildenumstring(_set: frozenset) -> 'Descriptor':
        return Descriptor(str, _set=_set)

    @staticmethod
    def buildenumupperstring(_set: frozenset) -> 'Descriptor':
        return Descriptor(UpperString.build, _set=_set)


DESCRIPTOR_STR = Descriptor(str, _validator=str)
DESCRIPTOR_BOOL = Descriptor(Boolean.build, _set=BOOL_SET)
DESCRIPTOR_INT = Descriptor(Integer.build, _validator=int)
DESCRIPTOR_INT_POSITIVE = Descriptor(Integer.build, _validator=vol.Range(min=0))
DESCRIPTOR_INT_PERCENT = Descriptor(Integer.build, _validator=vol.Range(min=0, max=100))

SCHEMA: Dict[str, Descriptor] = {
    SETUP_MODE: DESCRIPTOR_BOOL,
    CAMERA_ID: DESCRIPTOR_INT_POSITIVE,
    CAMERA_NAME: DESCRIPTOR_STR,
    TARGET_DIR: DESCRIPTOR_STR,
    LOG_FILE: DESCRIPTOR_STR,
    LOG_LEVEL: Descriptor.buildint(min=1, max=9),
    LOG_TYPE: Descriptor.buildenumupperstring(LOG_TYPE_SET),
    LOGFILE: DESCRIPTOR_STR,

    NETCAM_URL: DESCRIPTOR_STR,
    NETCAM_HIGHRES: DESCRIPTOR_STR,
    NETCAM_DECODER: DESCRIPTOR_STR,
    NETCAM_USERPASS: Descriptor(str, _validator=validate_userpass),
    NETCAM_USE_TCP: Descriptor.buildenumstring((VALUE_ON, VALUE_OFF, VALUE_FORCE)),
    NETCAM_KEEPALIVE: DESCRIPTOR_BOOL,

    WEBCONTROL_TLS: DESCRIPTOR_BOOL,

    STREAM_PORT: DESCRIPTOR_INT_POSITIVE,
    STREAM_AUTH_METHOD: Descriptor(Integer.build, _set=AUTH_MODE_SET),
    STREAM_AUTHENTICATION: DESCRIPTOR_STR,
    STREAM_TLS: DESCRIPTOR_BOOL,
    STREAM_GREY: DESCRIPTOR_BOOL,
    STREAM_MAXRATE: DESCRIPTOR_INT_POSITIVE,
    STREAM_MOTION: DESCRIPTOR_BOOL,
    STREAM_QUALITY: Descriptor.buildint(min=1, max=100),
    STREAM_PREVIEW_METHOD: Descriptor(Integer.build, _set=(0, 1, 2, 3, 4)),

    WIDTH: DESCRIPTOR_INT_POSITIVE,
    HEIGHT: DESCRIPTOR_INT_POSITIVE,
    FRAMERATE: Descriptor.buildint(min=2, max=100),
    MINIMUM_FRAME_TIME: DESCRIPTOR_INT_POSITIVE,
    ROTATE: Descriptor(Integer.build, _set=(0, 90, 180, 270)),
    FLIP_AXIS: Descriptor.buildenumstring((VALUE_NONE, VALUE_V, VALUE_H)),
    LOCATE_MOTION_MODE: Descriptor.buildenumstring((VALUE_OFF, VALUE_ON, VALUE_PREVIEW)),
    LOCATE_MOTION_STYLE: Descriptor.buildenumstring((VALUE_BOX, VALUE_REDBOX, VALUE_CROSS, VALUE_REDCROSS)),
    TEXT_LEFT: DESCRIPTOR_STR,
    TEXT_RIGHT: DESCRIPTOR_STR,
    TEXT_CHANGES: DESCRIPTOR_BOOL,
    TEXT_SCALE: Descriptor.buildint(min=1, max=10),
    TEXT_EVENT: DESCRIPTOR_STR,

    EMULATE_MOTION: DESCRIPTOR_BOOL,
    THRESHOLD: Descriptor.buildint(min=1),
    THRESHOLD_MAXIMUM: DESCRIPTOR_INT_POSITIVE,
    THRESHOLD_TUNE: DESCRIPTOR_BOOL,
    NOISE_LEVEL: Descriptor.buildint(min=1, max=255),
    NOISE_TUNE: DESCRIPTOR_BOOL,
    DESPECKLE_FILTER: DESCRIPTOR_STR,
    AREA_DETECT: DESCRIPTOR_STR,
    MASK_FILE: DESCRIPTOR_STR,
    MASK_PRIVACY: DESCRIPTOR_STR,
    SMART_MASK_SPEED: Descriptor.buildint(min=0, max=10),
    LIGHTSWITCH_PERCENT: DESCRIPTOR_INT_PERCENT,
    LIGHTSWITCH: DESCRIPTOR_INT_PERCENT,
    LIGHTSWITCH_FRAMES: Descriptor.buildint(min=1, max=1000),
    MINIMUM_MOTION_FRAMES: Descriptor.buildint(min=1, max=1000),
    EVENT_GAP: DESCRIPTOR_INT_POSITIVE,
    PRE_CAPTURE: Descriptor.buildint(min=0, max=100),
    POST_CAPTURE: DESCRIPTOR_INT_POSITIVE,

    ON_EVENT_START: DESCRIPTOR_STR,
    ON_EVENT_END: DESCRIPTOR_STR,
    ON_PICTURE_SAVE: DESCRIPTOR_STR,
    ON_MOTION_DETECTED: DESCRIPTOR_STR,
    ON_AREA_DETECTED: DESCRIPTOR_STR,
    ON_MOVIE_START: DESCRIPTOR_STR,
    ON_MOVIE_END: DESCRIPTOR_STR,
    ON_CAMERA_LOST: DESCRIPTOR_STR,
    ON_CAMERA_FOUND: DESCRIPTOR_STR,

    PICTURE_OUTPUT: Descriptor.buildenumstring((VALUE_OFF, VALUE_ON, VALUE_FIRST, VALUE_BEST)),
    PICTURE_OUTPUT_MOTION: DESCRIPTOR_BOOL,
    PICTURE_TYPE: Descriptor.buildenumstring(PICTURE_TYPE_SET),
    PICTURE_QUALITY: DESCRIPTOR_INT_PERCENT,
    PICTURE_EXIF: DESCRIPTOR_STR,
    PICTURE_FILENAME: DESCRIPTOR_STR,
    SNAPSHOT_INTERVAL: DESCRIPTOR_INT_POSITIVE,
    SNAPSHOT_FILENAME: DESCRIPTOR_STR,
    OUTPUT_PICTURES: Descriptor.buildenumstring((VALUE_OFF, VALUE_ON, VALUE_FIRST, VALUE_BEST)),
    OUTPUT_DEBUG_PICTURES: DESCRIPTOR_BOOL,
    QUALITY: DESCRIPTOR_INT_PERCENT,
    EXIF_TEXT: DESCRIPTOR_STR,

    MOVIE_OUTPUT: DESCRIPTOR_BOOL,
    MOVIE_OUTPUT_MOTION: DESCRIPTOR_BOOL,
    MOVIE_MAX_TIME: DESCRIPTOR_INT_POSITIVE,
    MOVIE_BPS: DESCRIPTOR_INT_POSITIVE,
    MOVIE_QUALITY: DESCRIPTOR_INT_PERCENT,
    MOVIE_CODEC: Descriptor.buildenumstring(MOVIE_CODEC_SET),
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
    FFMPEG_VIDEO_CODEC: Descriptor.buildenumstring(MOVIE_CODEC_SET),
    FFMPEG_DUPLICATE_FRAMES: DESCRIPTOR_BOOL,
    FFMPEG_PASSTHROUGH: DESCRIPTOR_BOOL,
    USE_EXTPIPE: DESCRIPTOR_BOOL,
    EXTPIPE: DESCRIPTOR_STR,

    TIMELAPSE_INTERVAL: DESCRIPTOR_INT_POSITIVE,
    TIMELAPSE_MODE: Descriptor.buildenumstring(TIMELAPSE_MODE_SET),
    TIMELAPSE_FPS: Descriptor.buildint(min=0, max=100),
    TIMELAPSE_CODEC: Descriptor.buildenumstring(TIMELAPSE_CODEC_SET),
    TIMELAPSE_FILENAME: DESCRIPTOR_STR

}

def build_value(key: str, value: str):
    """
    Polimorfic factory for typed params:
    key specifies a well-defined type usually so we parse and cast value
    accordingly.
    return None (untyped then) if value represent a None
    Fallback to plain 'str' if anything goes wrong
    """
    if value in NULL_SET:
        return None
    desc = SCHEMA.get(key)
    if desc:
        return desc.builder(value)

    if value in BOOL_SET:
        return Boolean.build(value)

    if value.lstrip("-").isnumeric():
        return Integer.build(value)

    return value