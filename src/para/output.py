"""The output tree: step 6 of the pipeline.

Every file a build produces is claimed, by the one step that produces it: a page (its
source path), a derived page, a copied folder, a minified asset, a site-wide file. Two
owners for one path is an error, not a race to the last write. Files are rewritten only
when their bytes change, so an unchanged page keeps its modification time. What is in
the output directory but no step claimed is reported (and removed with ``prune``): a
page that was deleted or renamed, or a file someone put there.

Media named by their content (extracted or copied next to a page, see
:mod:`para.media`) are owned by :data:`MEDIA`: two pages in one directory may both
produce the same file, and its name says it has the same bytes.
"""

from __future__ import annotations

import os
import threading
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Union

logger = getLogger(__name__)

MEDIA = "content-addressed media"


class OutputClash(RuntimeError):
    pass


class Output:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._owners: dict[str, str] = {}
        self._lock = threading.Lock()
        self.written = 0
        self.unchanged = 0

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
        path.write_bytes(new)
        with self._lock:
            self.written += 1
        return True

    def claim_tree(self, src: Path, dest: Path, owner: str) -> None:
        """Claim the files of the folder ``src`` as copied to ``dest``."""
        for dirpath, _, filenames in os.walk(src):
            for name in filenames:
                self.claim(dest / os.path.relpath(os.path.join(dirpath, name), src), owner)

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
            "output: %s files, %s written, %s unchanged, %s not produced by this build%s",
            len(self._owners),
            self.written,
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
