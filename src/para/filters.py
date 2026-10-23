"""Filters: the site's allow-list (``[filters.NAME]``), and the documents' choice from it.

A filter is code from something installed, named in the site's config, never a path in
the site: Python as an importable ``module:function`` (taking and returning a panflute
document), or Lua by name, found where packages install Lua filters (the environment's
``share/pandoc/filters/``, as pandoc-forge's do) or in pandoc's user data directory.

It runs at ``read`` (after reading, for every output) or ``render`` (for an output whose
profile names it). A read filter runs on a document if it is a ``default``, and a
document chooses with Quarto's key: ``filters: [texp, -pantable]`` turns ``texp`` on and
``pantable`` off; a render filter it names runs for all its outputs. Filters run in the
allow-list's order, whatever the document's: two documents with the same filters run
them the same way. A Lua render filter runs in the pandoc call that writes the output,
after the Python ones, so that it sees the output's format.
"""

from __future__ import annotations

import os
import subprocess  # nosec
import sys
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from panflute.tools import convert_text

if TYPE_CHECKING:
    from typing import Callable, Iterable, Mapping, Sequence

    from panflute import Doc

STAGES = ("read", "render")


class FilterError(ValueError):
    pass


def import_filter(spec: str) -> Any:
    """``module:function`` imported."""
    module, _, attr = spec.partition(":")
    if not attr:
        raise FilterError(f"{spec!r}: a filter is 'module:function'")
    obj = import_module(module)
    for name in attr.split("."):
        obj = getattr(obj, name)
    return obj


@lru_cache(maxsize=None)
def lua_dirs() -> tuple[Path, ...]:
    """Where installed Lua filters are: the environment's ``share/pandoc/filters/``, and
    pandoc's user data directory's ``filters/``."""
    res = [Path(sys.prefix) / "share" / "pandoc" / "filters"]
    if prefix := os.environ.get("CONDA_PREFIX"):
        res.append(Path(prefix) / "share" / "pandoc" / "filters")
    out = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=True).stdout  # nosec
    for line in out.splitlines():
        if line.startswith("User data directory:"):
            res.append(Path(line.partition(":")[2].strip()) / "filters")
    return tuple(dict.fromkeys(res))


def find_lua(name: str) -> Path:
    """The installed Lua filter ``name`` (``amsthm`` or ``amsthm.lua``)."""
    if "/" in name or "\\" in name:
        raise FilterError(f"lua = {name!r}: a filter's name, not a path (it is found where filters are installed)")
    file = name if name.endswith(".lua") else f"{name}.lua"
    for folder in lua_dirs():
        if (path := folder / file).is_file():
            return path
    raise FilterError(f"lua = {name!r}: not installed in {', '.join(map(str, lua_dirs()))}")


@dataclass(frozen=True)
class Filter:
    """A filter of the allow-list: Python (``function``) or Lua (``lua``)."""

    name: str
    at: str = "read"
    python: str = ""
    lua: str = ""
    inputs: tuple[str, ...] = ()
    default: bool = False

    @classmethod
    def from_spec(cls, name: str, spec: Mapping[str, Any]) -> Filter:
        unknown = set(spec) - {"python", "lua", "wasm", "at", "inputs", "default"}
        if unknown:
            raise FilterError(f"[filters.{name}]: unknown keys {sorted(unknown)}")
        if "wasm" in spec:
            raise FilterError(f"[filters.{name}]: WebAssembly filters are not supported yet")
        if ("python" in spec) == ("lua" in spec):
            raise FilterError(f"[filters.{name}]: one of python or lua")
        at = spec.get("at", "read")
        if at not in STAGES:
            raise FilterError(f"[filters.{name}]: at = {at!r}, one of {STAGES}")
        return cls(
            name=name,
            at=at,
            python=spec.get("python", ""),
            lua=spec.get("lua", ""),
            inputs=tuple(spec.get("inputs", ())),
            default=bool(spec.get("default", False)),
        )

    @property
    def function(self) -> Callable[[Doc], Doc]:
        return import_filter(self.python)

    @property
    def path(self) -> Path:
        return find_lua(self.lua)

    def check(self) -> None:
        """That what it names is installed."""
        self.function if self.python else self.path


def document_choice(value: Any, filters: Mapping[str, Filter], where: str) -> tuple[set[str], set[str]]:
    """A document's ``filters``: the names it turns on, and off (``-name``)."""
    if value is None:
        return set(), set()
    names = value if isinstance(value, list) else [value]
    on: set[str] = set()
    off: set[str] = set()
    for item in names:
        if not isinstance(item, str):
            raise FilterError(f"{where}: filters: {item!r}: a filter's name (Quarto's filters with options are not supported)")
        name = item[1:] if item.startswith("-") else item
        if name not in filters:
            hint = "a path is not allowed; " if "/" in name or name.endswith((".lua", ".py")) else ""
            raise FilterError(f"{where}: filters: {item!r}: {hint}add it to the site's [filters.NAME] first")
        (off if item.startswith("-") else on).add(name)
    return on, off


def chosen(
    filters: Mapping[str, Filter],
    stage: str,
    doc_filters: Any,
    where: str,
    ext: str = "",
    profile: Sequence[str] = (),
) -> list[Filter]:
    """The filters of ``stage`` that run on a document, in the allow-list's order: read
    filters by default or the document's choice (for input format ``ext``), render
    filters by the ``profile``'s or the document's."""
    on, off = document_choice(doc_filters, filters, where)
    res = []
    for f in filters.values():
        if f.at != stage or f.name in off:
            continue
        if stage == "read":
            if f.inputs and ext.lstrip(".") not in f.inputs:
                continue
            if f.default or f.name in on:
                res.append(f)
        elif f.name in profile or f.name in on:
            res.append(f)
    return res


def run(chain: Iterable[Filter], doc: Doc) -> Doc:
    """``doc`` through ``chain``: Python in process, consecutive Lua filters in one pandoc
    call."""
    lua: list[str] = []

    def flush(doc: Doc) -> Doc:
        if not lua:
            return doc
        args = [f"--lua-filter={path}" for path in lua]
        lua.clear()
        return convert_text(doc, input_format="panflute", output_format="panflute", standalone=True, extra_args=args)

    for f in chain:
        if f.lua:
            lua.append(str(f.path))
        else:
            doc = f.function(flush(doc))
    return flush(doc)
