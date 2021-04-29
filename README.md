![GitHub last commit](https://img.shields.io/github/last-commit/krahabb/motion_frontend?style=for-the-badge)
[![GitHub](https://img.shields.io/github/license/krahabb/motion_frontend?style=for-the-badge)](LICENCE)
[![hacs][hacsbadge]][hacs]


# Motion Frontend

This [homeassistant](https://www.home-assistant.io/) integration allows you to connect your HA instance directly to a running [@motion] daemon.
After succesfully connecting you will have all of the cameras in your motion setup available in you Home Assistant installation as streaming cameras thus allowing you to access your motion NVR camera streams (and recordings) from within the HA frontend 


## Installation

### HACS

In your HA frontend go to `HACS -> Integrations`, tap on the menu on the top-right corner and select `Custom repositories`.
Then select the `Category` (Integration) and type/paste this repository url: `https://github.com/krahabb/motion_frontend`.

You'll have to restart HA to let it recognize the new integration

### Manual installation

Download and copy the `custom_components/motion_frontend` directory into the `custom_components` folder on your homeassistant installation.

Depending on the type of HA installation you might have to follow specific instructions.

This is working for a standard 'core' installation but should work for any other flavour: remember to set the appropriate ownership and access rights on your copied files so the homeassistant user running your instance is able to read and execute the integration code.

Restart HA to let it play

## Setup

Before setting up the component a few considerations about motion:
Motion server has a peculiar hybrid config system which works really well if you carefully think about it: you can *and should* put most of the setup at the root motion.conf file and let the single camera.conf files just _tweaks_ parameters here and there. There are a lot of parameters (https://motion-project.github.io/4.3.2/motion_config.html#conversion_specifiers) used to format output from motion that you should really be able to put at use (for instance when building filenames for movies) in order to manage most of the configuration at the root level. Of course there might be a lot of options like thresholds or masks and other detection related parameters that need to be customized at the camera level but....keep an eye on that.
All this to say that this integration is built by 'guessing' the motion server configuration is really handled at the default config. This is rather different from what MotionEye does and also and mainly the reason why I just dropped that after a few tries, and started building this.
So to say, all the next configuration options work (or should likely) fine when motion is setup like that. If every camera has it's own setup this will probably mess up everything and this integration code is not ready for that (but I'm planning to slowly build-up to make it work in the wild)

A few hints:
- 'curl' is needed on the motion server in order to have webhooks working
- if you plan to share your motion recordings ('target_dir') with this integration and expose them as media in HA be sure they're accessible from HA itself (i.e. same filesystem, correct access rights)
- 'webcontrol_localhost' and 'stream_localhost' set this accordingly if your HA instance is on a different machine/environment than motion
- 'webcontrol_parms' in motion.conf should be set to '3' in order for the component to be able to access everything in the webctrl ui. If not, webhooks will not work for sure
- 'webcontrol_interface' could be set as you wish since this code will try to parse everything and adapt to the response actually received. Keep in mind that 'text mode' would be better for consistency in parsing especially if you're using a version which could have slightly modified its web interface. Text mode in motion should be rather stable across versions so if you don't mind go with it (set this option to '1')
- 'webcontrol_auth_method' no auth works for the best but also basic_auth ('1' in motion.conf). digest_auth not really tested: I'd expect it doesnt work
- 'webctrl_tls' works. Have a read below for the explanation on how to setup my component
- 'stream_tls' should work: the component should be prepared for that and handle the stream correctly but...you never know with TLS
- 'stream_auth_method' doesn't work beside 'None' (i.e. '0'). My code here is still some steps behind: not much, expect this to work sooner than later
- 'stream_port' works good when only configured at the root motion.conf. In motion 4.2 and later all the camera streams are accessible through a single port and my code works for this. The code should also work if you set different stream ports for different cameras (this is expecially true for motion 'legacy' pre 4.2). The component code will try to understand automatically which scenario is running and do the best to stream out of it. If something doesn't work please report it together with some hints on your motion.conf(s) and version

Once installed in HA you can add an entry configuration by going to the 'Integrations' pane in HA and look for 'Motion Frontend' (refresh browser cache if needed).
The configuration entry will ask you for:
- Host: the address of your motion server daemon
- Port: the port configured for the webctrl ui in motion: default = 8080
- Username,Password: fill in if you have configured authentication for webctrl ui (only tested BASIC_AUTH, DIGEST will probably not work)
- TLS Mode: use this to refine the TLS connection behaviour
  - Auto: tries to always connect whatever tls setup you have in motion. It basically tries different options automatically with or without TLS
  - None: uses http to connect to the webctrl
  - Default: uses https to connect with default python library settings. This could not work if there's some TLS mismatch like for instance 'untrusted CA' or other
  - Force: uses https but doesnt enforce security checks about the certificate used by the server (for instance self-signed certificate)
- Webhook mode: defines how (eventually) the webhook gets configured
  - Default: this will create a webhook in HA suitable to send motion events to HA itself. This option will not override any existing entry in your motion.conf if that's already used. Also, if the event entry is setup the first time by this code and you eventually reload the integration with a different setup (like maybe you changed the webhook address), the updated configuration for the webhook will not be sent since the event in motion is already configured by the previous setup
  - None: do not use any webhook. This will not overwrite any event command in motion.conf and HA will not receive state updates for the cameras
  - Force: this will set most of the event commands in 'motion.conf' to call the webhook in order to send these events to HA. HA will then update the camera state and publish some event data to the state attributes of the entity
- Webhook address: this is related to how the motion instance 'sees' HA in network terms. It could be an internal address if they're on the same local subnet, an external one if the HA instance is behind some address mapping feature (with respect to motion anyway) or the cloud address if HA is relayed through NabuCasa cloud
- Mount: this option will only work if your motion server and HA share the filesystem i.e. if HA _can really access locally_ the 'target_dir' configured in motion.conf. It will then expose the 'target_dir' path into the HA media library so to be able to use a media_player to play camera content. Keep in mind this will use the 'target_dir' at the root motion.conf and will not bother the parameter set in camera.conf files

## Supported motion daemon versions

This was originally developed on the latest motion release (4.3.2) so it should basically work on all of the newest webctrl ui(s). After that I've tried and tested on a debian 'official' apt release 4.1.1 and adapted to work on the legacy webctrl. Correct working will probably depend more on the configuration of the daemon than the version itself

Tested so far:
- 4.3.2
- 4.1.1

## How it works

The integration allows you to connect to any supported motion server instance through its own webctrl interface. When connected, extracts all the configuration parameters useful to expose the server cameras into HA. The cameras itself are implemented in HA terms as 'mjpeg' cameras and configured internally to report state (disconnected, idle, recording) and to expose their stream and still picture.

The state update is done through a webhook in HA and reconfiguring on the fly the motion daemon through its own webctrl so nothing has to be done manually here. There could be some 'caveats' though: if you configured your motion daemon with event scripts/commands you might consider what your needs are. The webhook actually just work to report state update to HA so that might not be that interesting to you if you already have implemented an event system on your motion instance.

This integration itself has various approaches to deal with it: by default it will only overwrite events in motion if they're not already configured (kind/relaxed approach). You can even decide you don't want to use webhook at all or 'Force' the integration to overwrite any whatever the actual configuration is. At any rate, the motion configuration updated on the fly will not be persisted to motion.conf (as per actual implementation: that might change in the future to avoid inconsistent behaviour in the model)
When configuring the webhook section of the integration you can decide wich type of address should be used in order for the motion instance to connect to the webhook. This is related to how your Home Assistant is configured and reachable over the network. You can choose to have HA calculate its own address in 'auto' mode or instruct to force a specific kind of address (internal, external, cloud). You don't have to explicitly set this address since HA already (should) know it better than you

Also, as a final, important, hint, the webhook gets invoked from motion by executing a 'curl' command so you *must* have it installed on the system running motion

If your motion server runs on the same HA machine (meaning they really share the / filesystem!) it can install the configured motion recording path ('target_dir') as a local media path in HA so to expose the recordings too through the media_player ui. This is still pretty raw and will just show you the path content allowing to browse and play content. It might be uncomfortable to use it when your recordings start to fill the filesystem and are rather unorganized (i.e. your motion server saves everything in the same folder). You might have already setup a filesystem tree to better suite your or organizational needs like separating recordings by camera and/or date: this will ease the browsing of your media content.

## References
- [@motion]

[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[@motion]: https://github.com/Motion-Project/motion
