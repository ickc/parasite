from __future__ import annotations

from pathlib import Path

import panflute as pf

from para.data import Post
from para.record import Record
from para.store import Store, hash_key


def record() -> Record:
    page = Post(Path("posts/a.md"), Path("posts"), Path(""), None)
    page.ast = pf.Doc(pf.Para(pf.Str("x")), metadata={"title": "A", "date": "2020-01-01"})
    return Record.from_page(page, True)


def test_store_round_trip(tmp_path):
    path = tmp_path / ".para" / "store.sqlite"
    store = Store(path)
    rec = record()
    store.put_read(rec.source, "k1", rec, ["a/b.svg"])
    store.put_render(rec.source, "r1", "<p>x</p>")
    store.renders = {"index.html": "d1"}
    store.save()

    again = Store(path)
    assert again.record(rec.source, "k1") == rec
    assert again.record(rec.source, "k2") is None
    assert again.claims(rec.source) == ["a/b.svg"]
    assert again.rendered(rec.source, "r1") and not again.rendered(rec.source, "r2")
    assert again.fragment(rec.source) == "<p>x</p>"
    assert again.renders == {"index.html": "d1"}
    assert Store(path, load=False).pages == {}


def test_keep_only_forgets_deleted_sources(tmp_path):
    store = Store(tmp_path / "s.sqlite")
    rec = record()
    store.put_read(rec.source, "k", rec, [])
    store.keep_only([])
    assert store.record(rec.source, "k") is None


def test_hash_key_separates_parts():
    assert hash_key("ab", "c") != hash_key("a", "bc")
