"""FUSE overlay filesystem that renames media files on the fly."""

import errno
import logging
import os
import threading
import time
from collections import OrderedDict

from fuse import FuseOSError, Operations

from .parser import transform_name

log = logging.getLogger("jellyfs")


class JellyFS(Operations):
    """
    Read-through overlay that renames media files on the fly.

    For every FUSE call the virtual (display) path is resolved back to
    the real source path before I/O is performed.  A per-directory
    name-mapping cache (TTL 1 s) keeps things fast without going stale.
    """

    def __init__(self, source: str, cfg: dict, writable: bool = False):
        self.root     = os.path.realpath(source)
        self.cfg      = cfg
        self.writable = writable
        self._lock    = threading.Lock()
        self._dcache: dict[str, tuple[float, dict[str, str]]] = {}
        self._ttl     = 1.0            # seconds

    # ── name translation helpers ──────────────────────────────────────

    def _vname(self, real_name: str) -> str:
        return transform_name(real_name, self.cfg)

    def _dir_map(self, real_dir: str, *, force: bool = False) -> dict[str, str]:
        """
        Build / return a {virtual_name: real_name} mapping for *real_dir*.

        Results are cached for up to ``_ttl`` seconds unless *force* is set.
        Collision disambiguation appends " (N)" before the extension.
        """
        now = time.monotonic()
        if not force:
            with self._lock:
                hit = self._dcache.get(real_dir)
                if hit and (now - hit[0] < self._ttl):
                    return hit[1]

        mapping: OrderedDict[str, str] = OrderedDict()
        counts: dict[str, int] = {}

        try:
            entries = sorted(os.listdir(real_dir))
        except OSError:
            return {}

        for rn in entries:
            vn = self._vname(rn)
            if vn in mapping:                       # collision
                counts.setdefault(vn, 1)
                counts[vn] += 1
                stem, ext = os.path.splitext(vn)
                vn = f"{stem} ({counts[vn]}){ext}"
                log.warning("Collision in %s: %r → %r", real_dir, rn, vn)
            mapping[vn] = rn

        with self._lock:
            self._dcache[real_dir] = (time.monotonic(), mapping)
        return mapping

    def _real(self, vpath: str) -> str:
        """Resolve a virtual (display) path to its real source path."""
        if vpath in ("", "/"):
            return self.root
        cur = self.root
        for part in vpath.strip("/").split("/"):
            if not part:
                continue
            dm = self._dir_map(cur)
            cur = os.path.join(cur, dm.get(part, part))
        return cur

    def _ro_guard(self):
        if not self.writable:
            raise FuseOSError(errno.EROFS)

    # ── directory operations ──────────────────────────────────────────

    def readdir(self, path, fh):
        dm = self._dir_map(self._real(path), force=True)
        yield "."
        yield ".."
        yield from dm

    def mkdir(self, path, mode):
        self._ro_guard(); os.mkdir(self._real(path), mode)

    def rmdir(self, path):
        self._ro_guard(); os.rmdir(self._real(path))

    # ── metadata ──────────────────────────────────────────────────────

    def getattr(self, path, fh=None):
        try:
            st = os.lstat(self._real(path))
        except OSError as e:
            raise FuseOSError(e.errno)
        return {k: getattr(st, k) for k in (
            "st_atime", "st_ctime", "st_gid", "st_mode",
            "st_mtime", "st_nlink", "st_size", "st_uid",
            "st_blocks", "st_blksize",
        )}

    def access(self, path, amode):
        if not os.access(self._real(path), amode):
            raise FuseOSError(errno.EACCES)

    def statfs(self, path):
        sv = os.statvfs(self._real(path))
        return {k: getattr(sv, k) for k in (
            "f_bavail", "f_bfree", "f_blocks", "f_bsize",
            "f_favail", "f_ffree", "f_files", "f_flag",
            "f_frsize", "f_namemax",
        )}

    def chmod(self, path, mode):
        self._ro_guard(); os.chmod(self._real(path), mode)

    def chown(self, path, uid, gid):
        self._ro_guard(); os.lchown(self._real(path), uid, gid)

    def utimens(self, path, times=None):
        self._ro_guard(); os.utime(self._real(path), times)

    # ── symlinks / hardlinks ──────────────────────────────────────────

    def readlink(self, path):
        return os.readlink(self._real(path))

    def symlink(self, target, name):
        self._ro_guard(); os.symlink(target, self._real(name))

    def link(self, target, name):
        self._ro_guard(); os.link(self._real(target), self._real(name))

    # ── file I/O ──────────────────────────────────────────────────────

    def open(self, path, flags):
        if not self.writable and (flags & (os.O_WRONLY | os.O_RDWR)):
            raise FuseOSError(errno.EROFS)
        return os.open(self._real(path), flags)

    def create(self, path, mode, fi=None):
        self._ro_guard()
        return os.open(
            self._real(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode
        )

    def read(self, path, length, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        self._ro_guard()
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        self._ro_guard()
        with open(self._real(path), "r+") as f:
            f.truncate(length)

    def flush(self, path, fh):
        if self.writable:
            try:
                os.fsync(fh)
            except OSError:
                pass
        return 0

    def release(self, path, fh):
        os.close(fh)

    def fsync(self, path, fdatasync, fh):
        if self.writable:
            os.fsync(fh)
        return 0

    # ── rename / unlink ───────────────────────────────────────────────

    def unlink(self, path):
        self._ro_guard(); os.unlink(self._real(path))

    def rename(self, old, new):
        self._ro_guard(); os.rename(self._real(old), self._real(new))

    # ── extended attributes ───────────────────────────────────────────

    def getxattr(self, path, name, position=0):
        try:
            return os.getxattr(self._real(path), name)
        except OSError as e:
            raise FuseOSError(e.errno)

    def listxattr(self, path):
        try:
            return os.listxattr(self._real(path))
        except OSError as e:
            raise FuseOSError(e.errno)

    def setxattr(self, path, name, value, options, position=0):
        self._ro_guard()
        try:
            os.setxattr(self._real(path), name, value, options)
        except OSError as e:
            raise FuseOSError(e.errno)

    def removexattr(self, path, name):
        self._ro_guard()
        try:
            os.removexattr(self._real(path), name)
        except OSError as e:
            raise FuseOSError(e.errno)
