"""What a source's read depends on, besides its own bytes: the files it touched.

A read records each file it uses (see :func:`recording`), with a stamp: a file's size and
modification time, a folder's listing, or that it is missing. The store keeps them with
the record, and a later build reads the source again only when one of them changed
(:func:`unchanged`). They are:

- what parasite resolves for it: the files its links and images name (or would, when
  missing), the media files it references and those they reference, its translation's
  primary, and its bibliography and style when it cites;
- the files and folders named in its text, as a path from its folder or the site's root:
  what a filter reads because the document names it (a table's CSV, a gallery's folder);
- what a filter reports with :func:`touch`.

What a filter reads without the document naming it, and without telling, is not seen:
``--full`` reads everything.
"""

from __future__ import annotations

import hashlib
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable, Iterator, Mapping, Optional

_current: ContextVar[Optional[dict[str, str]]] = ContextVar("para_deps", default=None)

# a path-like word: no scheme, a / in it or at its end, or a file extension
_PATHS = re.compile(r"(?<![\w:/.-])((?:\.{1,2}/)*[\w@+-][\w@+./-]*(?:/[\w@+.-]+|\.[A-Za-z0-9]{1,8}|/))")


# folders' stamps, once per build, and what is not an input (see :func:`fresh`)
_DIRS: dict[str, str] = {}
_IGNORED: list[str] = []


def fresh(ignored: Iterable[Path | str] = ()) -> None:
    """Forget the folders' stamps, at the start of a build; ``ignored`` are folders that
    are not inputs (the output, the store), never touched."""
    _DIRS.clear()
    _IGNORED[:] = [os.path.normpath(p) for p in ignored]


def stamp(path: Path) -> str:
    """A file's size and modification time; a folder's listing (recursive, with each
    file's); or ``missing``."""
    try:
        if path.is_dir():
            if (res := _DIRS.get(str(path))) is not None:
                return res
            h = hashlib.sha256()
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames.sort()
                for name in sorted(filenames):
                    h.update(stamp(Path(dirpath) / name).encode("utf-8") + b"\0")
                    h.update(os.path.join(dirpath, name).encode("utf-8") + b"\0")
            res = _DIRS[str(path)] = "dir " + h.hexdigest()
            return res
        st = path.stat()
    except OSError:
        return "missing"
    return f"{st.st_size} {st.st_mtime_ns}"


def touch(path: Path | str) -> None:
    """Record that the read in progress uses ``path`` (relative to the site), if a read
    is recording; for filters that read files the document does not name."""
    deps = _current.get()
    if deps is None:
        return
    key = os.path.normpath(path)
    if any(key == folder or key.startswith(folder + os.sep) or folder.startswith(key + os.sep) for folder in _IGNORED):
        return
    if key not in deps and not key.startswith(".."):
        deps[key] = stamp(Path(key))


@contextmanager
def recording() -> Iterator[dict[str, str]]:
    """The files touched in this context (this thread's)."""
    deps: dict[str, str] = {}
    token = _current.set(deps)
    try:
        yield deps
    finally:
        _current.reset(token)


def mentioned(source: Path, text: str) -> None:
    """Touch the existing files and folders ``text`` names, from ``source``'s folder or
    the site's root."""
    seen = set()
    for word in _PATHS.findall(text):
        word = word.rstrip(".")
        # no path is that long (a notebook's base64 is)
        if word in seen or len(word) > 255:
            continue
        seen.add(word)
        for base in (source.parent, Path(".")):
            path = Path(os.path.normpath(base / word))
            try:
                if path != Path(".") and path.exists():
                    touch(path)
            except OSError:
                pass


def unchanged(deps: Mapping[str, str]) -> bool:
    """Whether every file recorded is as it was."""
    return all(stamp(Path(path)) == value for path, value in deps.items())


def touch_all(paths: Iterable[Path | str]) -> None:
    for path in paths:
        touch(path)
