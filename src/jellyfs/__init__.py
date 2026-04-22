"""JellyFS — FUSE overlay presenting scene-tagged media with clean filenames.

Maps:
    Movie (2024) [tmdbid-123] - [Remux 2160p][TrueHD Atmos 7.1][DV HDR10][HEVC]-Group.mkv
To:
    Movie (2024) [tmdbid-123] - 4K | Bluray.mkv
"""

from .config import DEFAULT_CONFIG, DEFAULT_STREAMING_SERVICES, load_config
from .fs import JellyFS
from .parser import ParsedMedia, build_display_name, parse_filename, transform_name

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_STREAMING_SERVICES",
    "JellyFS",
    "ParsedMedia",
    "build_display_name",
    "load_config",
    "parse_filename",
    "transform_name",
]
