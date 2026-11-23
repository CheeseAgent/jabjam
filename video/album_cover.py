"""Find a local song's front cover and prepare one thumbnail for its opening title."""
from io import BytesIO
import json
import subprocess

from PIL import Image, ImageOps

from course import COVER_SUFFIXES

COVER_EDGE = 96


def _tile(source):
    size = (COVER_EDGE, COVER_EDGE)
    try:
        with Image.open(source) as image:
            image.thumbnail(size, Image.Resampling.LANCZOS)
            art = ImageOps.exif_transpose(image).convert("RGBA")
            return ImageOps.pad(art, size, method=Image.Resampling.LANCZOS, color=(0, 0, 0, 0))
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("Cannot decode album cover") from exc


def _embedded_cover(music):
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v",
        "-show_entries", "stream=index:stream_disposition=attached_pic:stream_tags=comment",
        "-of", "json", str(music),
    ], capture_output=True)
    if probe.returncode:
        return None
    pictures = [s for s in json.loads(probe.stdout).get("streams", [])
                if s.get("disposition", {}).get("attached_pic")]
    # An MP3 can include a back cover or booklet before the tagged front cover.
    pictures.sort(key=lambda s: "front" not in s.get("tags", {}).get("comment", "").lower())
    for picture in pictures:
        packet = subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-i", str(music),
            "-map", f"0:{picture['index']}", "-frames:v", "1", "-c:v", "copy", "-f", "image2pipe", "pipe:1",
        ], capture_output=True)
        if packet.returncode == 0 and packet.stdout:
            try:
                return _tile(BytesIO(packet.stdout))
            except ValueError:
                continue
    return None


def load_album_cover(picture, music):
    selection = picture.get("album_cover", "off")
    if selection == "off" or picture.get("title_style", "off") == "off":
        return None
    if selection != "auto":
        try:
            return _tile(selection)
        except ValueError as exc:
            raise ValueError(f"Cannot decode picture.album_cover: {selection}") from exc
    if music == "builtin:demo":
        return None
    embedded = _embedded_cover(music)
    if embedded is not None:
        return embedded
    try:
        siblings = sorted(music.parent.iterdir())
    except OSError:
        return None
    for path in siblings:
        if path.stem == music.stem and path.suffix.lower() in COVER_SUFFIXES and path.is_file():
            try:
                return _tile(path)
            except ValueError:
                continue
    return None
