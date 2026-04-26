"""Scene-tagged filename parser and display-name renderer."""

import re
from dataclasses import dataclass


# Title (Year) [tmdbid-ID] - …   (also handles tvdbid / imdbid)
_PREFIX = re.compile(
    r"^(?P<prefix>.+\[(?:tmdbid|tvdbid|imdbid)-[^\]]+\]"
    r"(?:\s*-\s*S\d+E\d+(?:-E?\d+)*)?)"
    r"\s*-\s*"
    r"(?P<rest>.+)$"
)

# ]GroupName.ext or ].ext at the very end  (release group is optional)
_GROUP_EXT = re.compile(r"\](?:-(?P<group>\w+))?(?P<ext>\..+)$")

# Source + optional resolution inside a bracket: "Remux 2160p", "SDTV", …
_SOURCE_RES = re.compile(
    r"^(?P<src>"
    r"(?:UHD\s+)?Remux|(?:BD|UHD)[-\s]?Remux|"
    r"Blu-?[Rr]ay|"
    r"WEBDL|WEB[-\s]?DL|WEBRip|WEB[-\s]?Rip|"
    r"HDTV|SDTV|DVDRip|BDRip|DVD"
    r")(?:[-\s]+(?P<res>\d{3,4}p)(?:\s+\w+)*)?$",
    re.IGNORECASE,
)

_VIDEO_CODECS = {c.upper() for c in [
    "HEVC", "H.265", "H265", "x265",
    "AVC", "H.264", "H264", "x264",
    "AV1", "VP9", "MPEG2",
]}

_AUDIO_HINTS = [
    "truehd", "dts", "ac3", "aac", "flac", "eac3",
    "e-ac-3", "dd+", "dd", "lpcm", "opus", "atmos", "pcm",
]


@dataclass
class ParsedMedia:
    """Structured representation of a scene-tagged media filename."""
    prefix:        str  = ""      # Title (Year) [tmdbid-ID]
    edition:       str  = ""      # Extended, Director's Cut, …
    resolution:    str  = ""      # 2160p, 1080p, …
    source_type:   str  = ""      # remux | encoded_disc | web | hdtv | sdtv | dvd
    streaming_svc: str  = ""      # uppercase key, e.g. "AMZN"
    dv_compat:     bool = False   # [Dolby Vision Compatibility] present
    dv:            bool = False   # any [DV...] tag present
    extension:     str  = ""      # .mkv  or  .eng.srt  etc.
    original:      str  = ""      # untouched input filename
    matched:       bool = False   # True if pattern was recognised


def parse_filename(name: str, services: dict) -> ParsedMedia:
    """
    Parse a scene-release filename into structured components.

    Returns matched=False if the name doesn't fit the expected pattern;
    callers should then use the original filename as-is.
    """
    info = ParsedMedia(original=name)

    m = _PREFIX.match(name)
    if not m:
        return info

    info.prefix = m.group("prefix")
    rest = m.group("rest")

    # ── extract release group + extension from the tail ──
    gm = _GROUP_EXT.search(rest)
    if not gm:
        return info

    info.extension = gm.group("ext")
    rest = rest[: gm.start() + 1]           # keep through the last ']'

    # ── split edition text from bracketed tags ──
    bpos = rest.find("[")
    if bpos < 0:
        return info

    info.edition = rest[:bpos].strip()
    tags = re.findall(r"\[([^\]]+)\]", rest[bpos:])

    # ── classify each tag ──
    svc_keys = {k.upper() for k in services}

    for tag in tags:
        t  = tag.strip()
        tl = t.lower()

        # Dolby Vision compatibility / profile-8 flag
        if "dolby vision compatibility" in tl:
            info.dv_compat = True
            continue

        # Bare DV tag (e.g. "DV", "DV HDR10") — Smart-TV-incompatible profile
        if tl == "dv" or tl.startswith("dv "):
            info.dv = True
            continue

        # Source + Resolution  (e.g. "Remux 2160p")
        sr = _SOURCE_RES.match(t)
        if sr:
            raw = sr.group("src").upper().replace("-", "").replace(" ", "")
            info.resolution = sr.group("res") or ""
            if raw in ("REMUX", "BDREMUX", "UHDREMUX"):
                info.source_type = "remux"
            elif raw in ("BLURAY", "BDRIP"):
                info.source_type = "encoded_disc"
            elif raw in ("WEBDL", "WEBRIP"):
                info.source_type = "web"
            elif raw == "HDTV":
                info.source_type = "hdtv"
            elif raw == "SDTV":
                info.source_type = "sdtv"
            elif raw in ("DVDRIP", "DVD"):
                info.source_type = "dvd"
            continue

        # Streaming service — strip trailing parenthetical qualifier
        # so "CR (Series)", "CR (Movies)", etc. all resolve to "CR".
        base = re.sub(r"\s*\([^)]*\)\s*$", "", t).upper()
        if base in svc_keys:
            info.streaming_svc = base
            continue

        # Video codec — not shown, skip
        if t.upper().replace(".", "") in _VIDEO_CODECS:
            continue

        # Audio — not shown, skip
        if any(kw in tl for kw in _AUDIO_HINTS):
            continue

        # Everything else (HDR tags, etc.) — silently ignored

    info.matched = True
    return info


def build_display_name(info: ParsedMedia, cfg: dict) -> str:
    """
    Assemble a clean display filename from parsed metadata.

    Format:  {prefix} - {edition} | {resolution} | {source} | {dv}.ext
    """
    if not info.matched:
        return info.original

    sep        = cfg["separator"]
    res_labels = cfg["resolution_labels"]
    src_labels = cfg["source_labels"]
    services   = cfg["streaming_services"]

    parts: list[str] = []

    # Edition  (e.g. "Extended")
    if info.edition:
        parts.append(info.edition)

    # Resolution  (e.g. "4K")
    rd = res_labels.get(info.resolution, info.resolution)
    if rd:
        parts.append(rd)

    # Source / service
    if info.source_type == "web":
        smap = {k.upper(): v for k, v in services.items()}
        src = smap.get(info.streaming_svc, src_labels.get("web_fallback", "WEB"))
        if src:
            parts.append(src)
    elif info.source_type in src_labels:
        if src_labels[info.source_type]:
            parts.append(src_labels[info.source_type])
    elif info.source_type:
        parts.append(info.source_type.title())

    # DV compatibility note
    if info.dv_compat:
        parts.append(cfg["dv_compat_label"])
    elif info.dv:
        parts.append(cfg["dv_label"])

    if parts:
        return f"{info.prefix} - {sep.join(parts)}{info.extension}"
    return info.original


def transform_name(name: str, cfg: dict) -> str:
    """Convenience: parse → build in one call."""
    return build_display_name(
        parse_filename(name, cfg["streaming_services"]), cfg
    )
