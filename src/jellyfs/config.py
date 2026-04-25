"""Default configuration and YAML overlay loader."""

import sys
from typing import Optional


DEFAULT_STREAMING_SERVICES: dict[str, str] = {
    "ABEMA":    "Abema",
    "ADN":      "Anime Digital Network",
    "AMZN":     "Prime Video",
    "ATVP":     "Apple TV+",
    "B-Global": "Bilibili Global",
    "Bilibili": "Bilibili",
    "CR":       "Crunchyroll",
    "CRAV":     "Crave",
    "CRIT":     "Criterion Channel",
    "DSCP":     "Discovery+",
    "DSNP":     "Disney+",
    "FUNI":     "Funimation",
    "GP":       "Google Play",
    "HIDIVE":   "HIDIVE",
    "HMAX":     "Max",               # legacy HBO Max tag
    "HTBM":     "HBO Max",           # older tag variant
    "HTSR":     "Hotstar",
    "HULU":     "Hulu",
    "IQIYI":    "iQIYI",
    "iT":       "iTunes",
    "KCW":      "KOCOWA",
    "MA":       "Movies Anywhere",
    "MAX":      "Max",
    "NF":       "Netflix",
    "NOW":      "NOW",
    "PCOK":     "Peacock",
    "PMTP":     "Paramount+",
    "ROKU":     "Roku",
    "SHO":      "Showtime",
    "STAN":     "Stan",
    "TVING":    "TVING",
    "VIKI":     "Viki",
    "VIU":      "Viu",
    "VRV":      "VRV",
    "VUDU":     "Vudu",
    "WAVVE":    "Wavve",
    "WeTV":     "WeTV",
    "YK":       "Youku",
}

DEFAULT_CONFIG: dict = {
    "resolution_labels": {
        "2160p": "4K",
        "1080p": "HD",
        "720p":  "720p",
        "480p":  "SD",
    },
    "source_labels": {
        "remux":        "Bluray",
        "encoded_disc": "Bluray (Compressed)",
        "web_fallback": "",
        "hdtv":         "HDTV",
        "sdtv":         "SDTV",
        "dvd":          "DVD",
    },
    "dv_compat_label": "Optimized for Smart TV",
    "dv_label": "Untouched Original",
    "separator": " | ",
    "streaming_services": DEFAULT_STREAMING_SERVICES,
}


def load_config(path: Optional[str] = None) -> dict:
    """Load DEFAULT_CONFIG, then layer any user YAML on top."""
    cfg = {k: (dict(v) if isinstance(v, dict) else v)
           for k, v in DEFAULT_CONFIG.items()}

    if path:
        try:
            import yaml
        except ImportError:
            sys.exit("PyYAML is required for config files:  pip install pyyaml")
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        for key in cfg:
            if key in user:
                if isinstance(cfg[key], dict) and isinstance(user[key], dict):
                    cfg[key].update(user[key])
                else:
                    cfg[key] = user[key]
    return cfg
