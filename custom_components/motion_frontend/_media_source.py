"""
    Local Media Source Implementation.

    This code actually works to browse motion recordings on a local path
    allowing to browse and expose the contents of the filesystem in motion 'target_dir'
    into the HA media browser UI

    sadly, the HA media player seems unable to play the content since the url I'm publishing
    in 'async_resolve_media' gets processed by the default 'media_source' implementation
    which only looks through configured paths in 'hass.config.media_dirs'

    Either I don't get the full picture or publishing local paths beside the official '/media'
    url is not allowed (which looks the most logical assumption here)

    In the end I've reverted to a kind of a trick: when configuring the motion config entry
    I'll inject the 'target_dir' into the HA configured and allowed media_dirs


"""
from __future__ import annotations

import mimetypes
from pathlib import Path

#from aiohttp import web
#from homeassistant.components.http import HomeAssistantView


from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_VIDEO,
    MEDIA_TYPE_VIDEO,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.const import (
    MEDIA_MIME_TYPES,
    MEDIA_CLASS_MAP
)
from homeassistant.components.media_source.error import MediaSourceError, Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import raise_if_invalid_path

from .const import (
    DOMAIN
)

async def async_get_media_source(hass: HomeAssistant):
    """Set up Netatmo media source."""
    return MotionRecordSource(hass)


class ItemInfo:

    def __init__(self, entry_id: str, target_dir: str, relativepath: str):
        self.entry_id: str = entry_id
        self.target_dir: str = target_dir
        self.path: Path = Path(target_dir, relativepath) if relativepath else Path(target_dir)


class MotionRecordSource(MediaSource):
    """Provide access to motion server recordings"""

    name: str = "Motion Server"


    def __init__(self, hass: HomeAssistant):
        super().__init__(DOMAIN)
        self.hass = hass


    @callback
    def async_parse_identifier(self, item: MediaSourceItem) -> ItemInfo:
        """Parse identifier."""
        if not item.identifier:
            raise Unresolvable("Invalid path.")

        split = item.identifier.split("/")

        entry_id = split[0]

        api = self.hass.data[DOMAIN].get(entry_id)
        if api is None:
            raise Unresolvable(f"Missing {DOMAIN} configuration entry.")

        iteminfo = ItemInfo(entry_id, api.client.target_dir, split[1] if len(split) > 1 else None)

        try:
            raise_if_invalid_path(str(iteminfo.path))
        except ValueError as err:
            raise Unresolvable("Invalid path.") from err

        return iteminfo


    async def async_resolve_media(self, item: MediaSourceItem) -> str:
        """Resolve media to a url."""
        iteminfo = self.async_parse_identifier(item)
        mime_type, _ = mimetypes.guess_type(str(iteminfo.path))
        return PlayMedia(f"/media/{item.identifier}", mime_type)


    async def async_browse_media(
        self, item: MediaSourceItem, media_types: tuple[str] = MEDIA_MIME_TYPES
    ) -> BrowseMediaSource:

        # root node for motion_frontend media
        # add a child for each configured server
        if item.identifier is None:
            base = BrowseMediaSource(
                domain=DOMAIN,
                identifier="",
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type=None,
                title=self.name,
                can_play=False,
                can_expand=True,
                children_media_class=MEDIA_CLASS_DIRECTORY,
            )

            base.children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry_id,
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_type=None,
                    title=api.client.unique_id,
                    can_play=False,
                    can_expand=True,
                )
                for entry_id, api in self.hass.data[DOMAIN].items()
            ]

            return base


        try:
            iteminfo: ItemInfo = self.async_parse_identifier(item)
        except Unresolvable as err:
            raise BrowseError(str(err)) from err

        return await self.hass.async_add_executor_job(self._browse_media, iteminfo)


    def _browse_media(self, iteminfo: ItemInfo):
        # iteminfo = (entry_id, target_dir, path)

        if not iteminfo.path.exists():
            raise BrowseError("Path does not exist.")

        return self._build_item_response(iteminfo, iteminfo.path)


    def _build_item_response(self, iteminfo: ItemInfo, path: Path, is_child=False):
        mime_type, _ = mimetypes.guess_type(str(path))
        is_file = path.is_file()
        is_dir = path.is_dir()

        # Make sure it's a file or directory
        if not is_file and not is_dir:
            return None

        # Check that it's a media file
        if is_file and (
            not mime_type or mime_type.split("/")[0] not in MEDIA_MIME_TYPES
        ):
            return None

        title = path.name
        if is_dir:
            title += "/"

        media_class = MEDIA_CLASS_MAP.get(
            mime_type and mime_type.split("/")[0], MEDIA_CLASS_DIRECTORY
        )

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{iteminfo.entry_id}/{path.relative_to(iteminfo.target_dir)}",
            media_class=media_class,
            media_content_type=mime_type or "",
            title=title,
            can_play=is_file,
            can_expand=is_dir,
        )

        if is_file or is_child:
            return media

        # Append first level children
        media.children = []
        for child_path in path.iterdir():
            child = self._build_item_response(iteminfo, child_path, True)
            if child:
                media.children.append(child)

        # Sort children showing directories first, then by name
        media.children.sort(key=lambda child: (child.can_play, child.title))

        return media


