# JellyFS

A FUSE overlay that presents scene-tagged media files with clean, Jellyfin-friendly names.

```
Movie (2024) [tmdbid-123] - [Remux 2160p][TrueHD Atmos 7.1][DV HDR10][HEVC]-Group.mkv
Movie (2024) [tmdbid-123] - 4K | Bluray.mkv
```

The source tree is untouched; the rename only exists in the mount.

## Install (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Dry run — print what would be renamed
python -m jellyfs /media/movies --preview

# Mount (read-only)
python -m jellyfs /media/movies /mnt/jellyfs -f

# Mount with custom config
python -m jellyfs /media/movies /mnt/jellyfs -c config.yaml -f

# Unmount
fusermount -u /mnt/jellyfs
```

Run from `src/` or add it to `PYTHONPATH`.

## Docker

Requires `SYS_ADMIN` + `/dev/fuse` and shared mount propagation on the target so the FUSE mount is visible on the host.

```bash
sudo mkdir -p /mnt/jellyfs
```

Prebuilt image: `ghcr.io/eebette/jellyfs:latest` (published by `.github/workflows/publish.yml` on push to `main` and version tags).

### `docker run`

```bash
docker run -d --name jellyfs --restart unless-stopped \
  --cap-add SYS_ADMIN \
  --device /dev/fuse \
  --security-opt apparmor=unconfined \
  -v /tank/media/content/Videos:/media/source:ro \
  --mount type=bind,source=/mnt/jellyfs,target=/media/mount,bind-propagation=rshared \
  ghcr.io/eebette/jellyfs:latest
```

Dry run against a host path:

```bash
docker run --rm \
  -v /tank/media/content/Videos:/media/source:ro \
  ghcr.io/eebette/jellyfs:latest /media/source --preview
```

### `docker compose` (JellyFS + Jellyfin)

```bash
docker compose up -d --build
# Jellyfin: http://localhost:8096
```

Env vars honored by `docker-compose.yml`:

| Var            | Default                        |
| -------------- | ------------------------------ |
| `MEDIA_SOURCE` | `/tank/media/content/Videos`   |
| `MEDIA_MOUNT`  | `/mnt/jellyfs`                 |
| `TZ`           | `America/Los_Angeles`          |

Jellyfin binds the shared mount with `rslave` propagation and waits on a `mountpoint -q` healthcheck.

## Config

Override any default via YAML and pass with `-c`:

```yaml
separator: " · "
source_labels:
  web_fallback: "WEB"
streaming_services:
  AMZN: "Amazon"
```

See `src/jellyfs/config.py` for the full defaults.

## Radarr / Sonarr setup

JellyFS relies on release tags being present in the filename, so configure your media management to emit them:

- In **Settings → Media Management**, include `{[Quality Full]}` and `{[Custom Formats]}` **after a hyphen** in your rename format. See the [Jellyfin "multiple versions" guide](https://jellyfin.org/docs/general/server/media/movies/#multiple-versions) for the surrounding context.
- For each streaming-service custom format, check **Include Custom Format when Renaming**. Otherwise the `AMZN` / `NF` / `DSNP` / etc. tag never lands in the filename and JellyFS falls back to the generic `WEB` label.
- Import the streaming-service custom formats from [TRaSH Guides → Streaming Services](https://trash-guides.info/Sonarr/sonarr-collection-of-custom-formats/#streaming-services_1) so the tags Radarr/Sonarr produce match the services recognized in `src/jellyfs/config.py`.

## Troubleshooting

**Mount not visible on the host (only inside the container).** Your host's propagation isn't `shared` on the mount target. Make it so:

```bash
sudo mount --bind /mnt/jellyfs /mnt/jellyfs
sudo mount --make-rshared /mnt/jellyfs
```

**`fuse: mount failed: Operation not permitted` on Debian/Ubuntu.** Docker's default AppArmor profile blocks FUSE mount syscalls. Add:

```
--security-opt apparmor=unconfined
```

(or `security_opt: [apparmor:unconfined]` in compose).

**`fusermount: option allow_other only allowed if 'user_allow_other' is set in /etc/fuse.conf`.** Drop `--allow-other` from the command, or ensure the Dockerfile's `echo "user_allow_other" >> /etc/fuse.conf` line ran (rebuild the image).

**Jellyfin sees an empty directory.** Start order — Jellyfin bind-mounted the target before JellyFS populated it, and propagation isn't forwarding new mounts. Check that Jellyfin's volume uses `propagation: rslave` and that the host target is `shared` (see first item).
