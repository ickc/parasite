"""The output tree: step 6 of the pipeline.

Every file a build produces is claimed, by the one step that produces it: a page (its
source path), a derived page, a copied folder, a bundled asset, a site-wide file. Two
owners for one path is an error, not a race to the last write. Files are rewritten only
when their bytes change, so an unchanged page keeps its modification time. What is in
the output directory but no step claimed is reported (and removed with ``prune``): a
page that was deleted or renamed, or a file someone put there.

Copied files (``[files]``, media) share their source's blocks where the filesystem lets
them (:func:`place`): nothing is duplicated on disk when the output is on the sources'
filesystem. Every write replaces the file (a new file renamed over it), so nothing is
ever written through a link into a source.

Media named by their content (extracted or copied next to a page, see
:mod:`para.media`) are owned by :data:`MEDIA`: two pages in one directory may both
produce the same file, and its name says it has the same bytes.
"""

from __future__ import annotations

import os
import shutil
import threading
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Union

logger = getLogger(__name__)

MEDIA = "content-addressed media"

# linux/fs.h: share a file's blocks, copy-on-write (XFS, Btrfs)
FICLONE = 0x40049409
# modification times compared within this, as a filesystem may keep them coarser (CIFS:
# 100 ns)
MTIME_SLACK_NS = 1_000_000


def _temporary(dest: Path) -> Path:
    """A file beside ``dest`` to write and rename over it, unique to this thread."""
    return dest.with_name(f".{dest.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def _reflink(src: Path, dest: Path) -> None:
    import fcntl  # not on Windows: an ImportError, an OSError

    with open(src, "rb") as s, open(dest, "wb") as d:
        fcntl.ioctl(d.fileno(), FICLONE, s.fileno())


def place(src: Path, dest: Path) -> str:
    """Make ``dest`` a file with ``src``'s bytes and modification time, sharing its blocks
    where possible: a reflink (copy-on-write, so either may change later), else a hard
    link (the same filesystem), else a copy (another filesystem). ``dest`` is replaced
    whole. Returns which: "reflink", "link" or "copy"."""
    tmp = _temporary(dest)
    try:
        try:
            _reflink(src, tmp)
            shutil.copystat(src, tmp)
            how = "reflink"
        except (ImportError, OSError):
            tmp.unlink(missing_ok=True)
            try:
                os.link(src, tmp)
                how = "link"
            except OSError:
                shutil.copy2(src, tmp)
                how = "copy"
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return how


def same_file(src: os.stat_result, dest: os.stat_result) -> bool:
    """Whether ``dest`` is ``src`` placed (:func:`place`) and unchanged since: one file,
    or the same size and modification time."""
    return (src.st_ino, src.st_dev) == (dest.st_ino, dest.st_dev) or (
        src.st_size == dest.st_size and abs(src.st_mtime_ns - dest.st_mtime_ns) < MTIME_SLACK_NS
    )


class OutputClash(RuntimeError):
    pass


class Output:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._owners: dict[str, str] = {}
        self._lock = threading.Lock()
        self.written = 0
        self.unchanged = 0
        # placed files by how: reflink, link, copy
        self.placed: dict[str, int] = {}

    def _key(self, path: Path) -> str:
        return Path(os.path.relpath(path, self.root)).as_posix()

    def claim(self, path: Path, owner: str) -> None:
        """Record that ``owner`` produces ``path`` (in the output directory)."""
        key = self._key(path)
        if key.startswith("../"):
            raise OutputClash(f"{owner} writes {path}, outside the output directory {self.root}")
        with self._lock:
            previous = self._owners.setdefault(key, owner)
        if previous != owner:
            raise OutputClash(f"{key} is produced by both {previous} and {owner}")

    def write(self, path: Path, data: Union[str, bytes], owner: str) -> bool:
        """Claim ``path`` and write ``data`` to it unless it has those bytes already;
        True if it was written."""
        self.claim(path, owner)
        new = data.encode("utf-8") if isinstance(data, str) else data
        try:
            if path.read_bytes() == new:
                with self._lock:
                    self.unchanged += 1
                return False
        except FileNotFoundError:
            path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _temporary(path)
        try:
            tmp.write_bytes(new)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        with self._lock:
            self.written += 1
        return True

    def copy(self, src: Path, dest: Path, owner: str) -> bool:
        """Claim ``dest`` and place ``src`` there (:func:`place`) unless it is there
        already (:func:`same_file`); True if it was placed."""
        self.claim(dest, owner)
        st = src.stat()
        try:
            if same_file(st, dest.stat()):
                with self._lock:
                    self.unchanged += 1
                return False
        except FileNotFoundError:
            dest.parent.mkdir(parents=True, exist_ok=True)
        how = place(src, dest)
        with self._lock:
            self.written += 1
            self.placed[how] = self.placed.get(how, 0) + 1
        return True

    def claim_tree(self, src: Path, dest: Path, owner: str) -> list[tuple[Path, Path]]:
        """Claim the files of the folder ``src`` as copied to ``dest``; the pairs (source,
        output path), to :meth:`copy`."""
        pairs = []
        for dirpath, _, filenames in os.walk(src):
            for name in filenames:
                path = Path(dirpath) / name
                pairs.append((path, dest / path.relative_to(src)))
                self.claim(pairs[-1][1], owner)
        return pairs

    def unclaimed(self) -> list[Path]:
        """Files in the output directory that no step produced, sorted."""
        res = []
        for dirpath, _, filenames in os.walk(self.root):
            for name in filenames:
                path = Path(dirpath) / name
                if self._key(path) not in self._owners:
                    res.append(path)
        return sorted(res)

    def finish(self, prune: bool = False) -> list[Path]:
        """Report what was written, and what is there that the build did not produce
        (removed if ``prune``). Returns those paths."""
        stale = self.unclaimed()
        logger.info(
            "output: %s files, %s written%s, %s unchanged, %s not produced by this build%s",
            len(self._owners),
            self.written,
            "".join(f", {n} by {how}" for how, n in sorted(self.placed.items())),
            self.unchanged,
            len(stale),
            " (removed)" if prune and stale else "",
        )
        for path in stale[:20]:
            logger.info("not produced by this build: %s", path)
        if prune:
            for path in stale:
                path.unlink()
        return stale
