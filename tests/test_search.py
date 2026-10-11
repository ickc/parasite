from __future__ import annotations

import json
from pathlib import Path

import pytest

from para.output import Output
from para.record import Record
from para.search import _cbor_dump, _cbor_load, write_pagefind

pytest.importorskip("pagefind")


def records() -> list[Record]:
    return [
        Record(
            source=f"p{i}.md",
            out_path=f"p{i}/index.html",
            url=f"p{i}/",
            post=True,
            title=f"P{i}",
            lang="zh_tw" if i % 5 == 0 else "en",
            category=f"c{i % 3}",
            tags=tuple(sorted({f"t{i * j % 13}" for j in range(1, 4)})),
            text=f"word{i} common text {i % 7}",
        )
        for i in range(40)
    ]


def test_cbor_round_trip():
    value = ["1.5.2", [["en_abc", 4], [b"\x00\x01", 1 << 20]], [], ["x" * 30, list(range(30))]]
    data = _cbor_dump(value)
    assert _cbor_load(data) == (value, len(data))


def test_pagefind_stable(tmp_path):
    """The same records give the same files, filters (tags, categories) and all."""
    built = []
    for run in range(3):
        out = tmp_path / str(run)
        output = Output(out)
        write_pagefind(records(), out, output, "zh_tw")
        built.append({p.relative_to(out): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()})
        assert not output.unclaimed()
    assert built[0] == built[1] == built[2]
    assert any(p.parts[1] == "filter" for p in built[0])
    # one index, in the site's language, for pages in any
    assert list(json.loads(built[0][Path("pagefind/pagefind-entry.json")])["languages"]) == ["zh-tw"]
