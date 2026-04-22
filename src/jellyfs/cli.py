"""Command-line entry point and preview (dry-run) walker."""

import argparse
import logging
import os
import sys

from fuse import FUSE

from .config import load_config
from .fs import JellyFS
from .parser import transform_name

log = logging.getLogger("jellyfs")


def preview(source: str, cfg: dict):
    """Walk source and print every rename that would be applied."""
    root    = os.path.realpath(source)
    changed = total = 0

    for dirpath, _dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        for fn in sorted(files):
            total += 1
            dn = transform_name(fn, cfg)
            if dn != fn:
                changed += 1
                loc = f"{rel}/" if rel != "." else ""
                print(f"  {loc}{fn}")
                print(f"  → {dn}")
                print()

    print(f"─── {changed}/{total} files would be renamed ───")


def main():
    ap = argparse.ArgumentParser(
        prog="jellyfs",
        description="Mount a media library with clean filenames for Jellyfin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s /media/movies --preview              # dry-run
  %(prog)s /media/movies /mnt/jellyfin           # mount (read-only)
  %(prog)s /media/movies /mnt/jellyfin -c cfg.yaml -f --debug
  fusermount -u /mnt/jellyfin                    # unmount
        """,
    )
    ap.add_argument("source",     help="Source media directory")
    ap.add_argument("mountpoint", nargs="?",
                    help="Mount point (omit for --preview)")
    ap.add_argument("-c", "--config", metavar="YAML",
                    help="Optional YAML config (overrides defaults)")
    ap.add_argument("--preview",  action="store_true",
                    help="Print renames without mounting")
    ap.add_argument("--writable", action="store_true",
                    help="Allow writes through the mount (default: read-only)")
    ap.add_argument("-f", "--foreground", action="store_true",
                    help="Stay in foreground")
    ap.add_argument("--debug",    action="store_true",
                    help="Verbose logging (implies --foreground)")
    ap.add_argument("--allow-other", action="store_true",
                    help="Let other users access the mount")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    if not os.path.isdir(args.source):
        sys.exit(f"Error: source '{args.source}' is not a directory")

    cfg = load_config(args.config)

    if args.preview:
        preview(args.source, cfg)
        return

    if not args.mountpoint:
        sys.exit("Error: mountpoint required (or use --preview)")

    os.makedirs(args.mountpoint, exist_ok=True)

    fs = JellyFS(args.source, cfg, writable=args.writable)

    log.info("Mounting  %s  →  %s  (read-%s)",
             args.source, args.mountpoint,
             "write" if args.writable else "only")

    FUSE(
        fs,
        args.mountpoint,
        foreground=args.foreground or args.debug,
        nothreads=False,
        allow_other=args.allow_other,
        ro=not args.writable,
    )
