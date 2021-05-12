
from .motionclient import TlsMode

DOMAIN = "motion_frontend"
PLATFORMS = ["camera", "alarm_control_panel"]


CONF_PORT_DEFAULT = 8080

# various enum modes for option 'select'
CONF_OPTION_NONE = "none"
CONF_OPTION_DEFAULT = "default"
CONF_OPTION_FORCE = "force"
CONF_OPTION_AUTO = "auto"
CONF_OPTION_INTERNAL = "internal"
CONF_OPTION_EXTERNAL = "external"
CONF_OPTION_CLOUD = "cloud"
CONF_OPTION_CONNECTION = "connection"
CONF_OPTION_ALARM = "alarm"


CONF_TLS_MODE = "tls_mode"
CONF_TLS_MODE_OPTIONS = (
    CONF_OPTION_AUTO, # best-effort: tries whatever to connect
    CONF_OPTION_NONE, # do not use tls/https
    CONF_OPTION_DEFAULT, # use standard tls/https with default policies (i.e. correct CA and so)
    CONF_OPTION_FORCE # use tls/https with 'relaxed' policies (suitable for self signed certs)
)

MAP_TLS_MODE = {
    CONF_OPTION_AUTO: TlsMode.AUTO,
    CONF_OPTION_NONE: TlsMode.NONE,
    CONF_OPTION_DEFAULT: TlsMode.STRICT,
    CONF_OPTION_FORCE: TlsMode.RELAXED
}

# option for webhooks: install webhook to register motion sourced events
CONF_WEBHOOK_MODE = "webhook_mode"
CONF_WEBHOOK_MODE_OPTIONS = (
    CONF_OPTION_DEFAULT, # install a webhook and set motion event handlers only when they're empty
    CONF_OPTION_NONE, # do not install webhooks: we will not receive status updates for cameras
    CONF_OPTION_FORCE # install a webhook and set motion event handlers overwriting any existing motion conf
)

CONF_WEBHOOK_ADDRESS = "webhook_address"
CONF_WEBHOOK_ADDRESS_OPTIONS = (
    CONF_OPTION_DEFAULT, # use whatever HA thinks is the best as an address to publish
    CONF_OPTION_INTERNAL, # force whatever HA thinks is the best as an internal address
    CONF_OPTION_EXTERNAL, # force whatever HA thinks is the best as an external address (cloud address as a fallback)
    CONF_OPTION_CLOUD # force cloud address
)

# option media_source: try to expose the motion target_dir as a media library path in HA
CONF_MEDIASOURCE = "media_source"

# OptionsFlow: async_step_alarm
# list of camera ids to 'disarm' under different alarm arming state
# by default an empty list in conf will arm all of the cameras
CONF_ALARM_DISARMHOME_CAMERAS = "disarmhome_cameras"
CONF_ALARM_DISARMAWAY_CAMERAS = "disarmaway_cameras"
CONF_ALARM_DISARMNIGHT_CAMERAS = "disarmnight_cameras"
CONF_ALARM_DISARMBYPASS_CAMERAS = "disarmbypass_cameras"
CONF_ALARM_PAUSE_DISARMED = "pause_disarmed" # if a camera is 'disarmed' pause motion detection



# a bunch of attributes to add to the state
EXTRA_ATTR_FILENAME = "filename"
EXTRA_ATTR_EVENT_ID = "event_id"
EXTRA_ATTR_TRIGGERED = "triggered"
EXTRA_ATTR_PAUSED = "paused"
EXTRA_ATTR_CONNECTED = "connected"
EXTRA_ATTR_LAST_TRIGGERED = "last_triggered" # alarm extra_attr: entity id of last alarm triggering camera
EXTRA_ATTR_LAST_PROBLEM = "last_problem" # alarm extra_attr: entity id of last alarm 'problem' camera


ON_EVENT_START = "on_event_start" # start of motion
ON_MOTION_DETECTED = "on_motion_detected" # motion continue
ON_AREA_DETECTED = "on_area_detected" # motion inside predefined area
ON_EVENT_END = "on_event_end" # end of motion
ON_MOVIE_START = "on_movie_start"
ON_MOVIE_END = "on_movie_end"
ON_PICTURE_SAVE = "on_picture_save"
ON_CAMERA_FOUND = "on_camera_found"
ON_CAMERA_LOST = "on_camera_lost"
"""
We only manage events for what we care of.
also, ON_MOTION_DETECTED is pretty rough since it looks it get shot on every frame
"""
MANAGED_EVENTS = (
    ON_CAMERA_FOUND, ON_CAMERA_LOST,
    ON_EVENT_START, ON_EVENT_END,
    ON_MOVIE_START, ON_MOVIE_END
)
