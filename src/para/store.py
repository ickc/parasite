"""The record store: what makes a build incremental.

For each source the store keeps its record (see :mod:`para.record`), the key it was read
under, the files its read wrote into the output (media), the keys its outputs were
rendered under, and its feed fragment. A build re-reads a source only when its read key changed
and re-renders a page only when its render key changed, or when a file it produced is
gone from the output. A full build is the same code with an empty store.

The **site key** covers what every page depends on: the code (every Python module
loaded, the installed distributions, parasite's package data), pandoc's version and data
directory, the site's config, and the files its config names for every page (see
:meth:`para.site.Config.site_files`). A change to any of them re-reads every source. A
**read key** adds the source's bytes; and a record is used only while the files its read
touched are unchanged (:mod:`para.deps`: its media, its bibliography if it cites, what
it names). A **render key** adds what a page's render takes from the rest of the site:
its copyright years, its link to a report, its translations. Derived pages are keyed by
their AST.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess  # nosec
import sys
from contextlib import closing
from importlib.metadata import distributions
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

from .deps import stamp
from .record import Record

if TYPE_CHECKING:
    from typing import Any, Iterable, Optional

logger = getLogger(__name__)

SCHEMA = 4


def hash_key(*parts: Any) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part if isinstance(part, bytes) else str(part).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def _stat(path: Path) -> str:
    try:
        st = path.stat()
    except OSError:
        return f"{path} missing"
    return f"{path} {st.st_size} {st.st_mtime_ns}"


def _tree(root: Path, skip: Iterable[Path] = ()) -> list[str]:
    """Stat lines of the files under ``root``, but not under ``skip``, sorted."""
    skip = {Path(os.path.abspath(p)) for p in skip}
    res = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(os.path.abspath(dirpath))
        dirnames[:] = sorted(d for d in dirnames if here / d not in skip and not d.startswith(".") and d != "__pycache__")
        res += [_stat(Path(dirpath) / name) for name in sorted(filenames) if here / name not in skip]
    return res


def code_stamp() -> str:
    """The code a build runs: the files of the loaded modules, parasite's package data
    and the installed distributions."""
    files = sorted({f for m in list(sys.modules.values()) if (f := getattr(m, "__file__", None))})
    package = Path(__file__).parent
    dists = sorted(f"{d.metadata['Name']} {d.version}" for d in distributions())
    return hash_key(*map(lambda f: _stat(Path(f)), files), *_tree(package), *dists)


def pandoc_stamp() -> str:
    version = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=True).stdout  # nosec
    datadir = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return hash_key(version, *_tree(Path(datadir) / "pandoc"))


def site_key(config_repr: str, files: Iterable[str]) -> str:
    """See the module's docstring. ``files`` are the site's files every page depends on."""
    parts = {
        "code": code_stamp(),
        "pandoc": pandoc_stamp(),
        "config": hash_key(config_repr),
        "files": hash_key(*(f"{f} {stamp(Path(f))}" for f in files)),
    }
    for name, value in parts.items():
        logger.debug("site key: %s %s", name, value[:12])
    return hash_key(SCHEMA, *parts.values())


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Store:
    """The store's rows in memory, loaded at the start of a build and saved at its end."""

    def __init__(self, path: Optional[Path], load: bool = True) -> None:
        """``path`` None keeps nothing; ``load`` False starts empty (a full build) and
        saves over what is there."""
        self.path = path
        self.pages: dict[str, dict[str, Any]] = {}
        self.renders: dict[str, str] = {}
        if path is None or not load or not path.exists():
            return
        try:
            # closing: a connection's own `with` commits, but does not close
            with closing(sqlite3.connect(path)) as db:
                if db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone() != (str(SCHEMA),):
                    return
                for source, row in db.execute("SELECT source, row FROM pages"):
                    self.pages[source] = json.loads(row)
                self.renders = dict(db.execute("SELECT out_path, key FROM renders"))
        except sqlite3.Error as e:
            logger.warning("store %s unreadable (%s): a full build", path, e)
            self.pages, self.renders = {}, {}

    def record(self, source: str, read_key: str) -> Optional[Record]:
        """The source's record, if it was read under ``read_key``."""
        row = self.pages.get(source)
        if row is None or row["read_key"] != read_key:
            return None
        return Record.from_json(row["record"])

    def claims(self, source: str) -> list[str]:
        return self.pages[source]["claims"]

    def put_read(self, source: str, read_key: str, record: Record, claims: list[str], deps: dict[str, str]) -> None:
        self.pages[source] = {"read_key": read_key, "record": record.to_json(), "claims": claims, "deps": deps}

    def deps(self, source: str) -> dict[str, str]:
        """The files the source's read touched, and their stamps (para.deps)."""
        return self.pages.get(source, {}).get("deps", {})

    def rendered(self, source: str, profile: str, render_key: str) -> bool:
        """Whether the source's output in ``profile`` was rendered under ``render_key``."""
        return self.pages.get(source, {}).get("renders", {}).get(profile) == render_key

    def put_render(self, source: str, profile: str, render_key: str) -> None:
        self.pages[source].setdefault("renders", {})[profile] = render_key

    def put_fragment(self, source: str, fragment: Optional[str]) -> None:
        self.pages[source]["fragment"] = fragment

    def fragment(self, source: str) -> Optional[str]:
        return self.pages.get(source, {}).get("fragment")

    def keep_only(self, sources: Iterable[str]) -> None:
        keep = set(sources)
        self.pages = {k: v for k, v in self.pages.items() if k in keep}

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.unlink(missing_ok=True)
        with sqlite3.connect(tmp) as db:
            db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("CREATE TABLE pages (source TEXT PRIMARY KEY, row TEXT)")
            db.execute("CREATE TABLE renders (out_path TEXT PRIMARY KEY, key TEXT)")
            db.execute("INSERT INTO meta VALUES ('schema', ?)", (str(SCHEMA),))
            db.executemany("INSERT INTO pages VALUES (?, ?)", ((k, json.dumps(v)) for k, v in sorted(self.pages.items())))
            db.executemany("INSERT INTO renders VALUES (?, ?)", sorted(self.renders.items()))
        db.close()
        os.replace(tmp, self.path)
