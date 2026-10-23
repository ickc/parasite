from __future__ import annotations

import os

from para import deps


def test_recording_and_stamps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "posts").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data/t.csv").write_text("a,b\n")
    (tmp_path / "gallery").mkdir()
    (tmp_path / "gallery/1.jpg").write_text("")
    source = tmp_path / "posts/a.md"
    source.write_text("A table from ../data/t.csv, photos in gallery/ and e.g. 3.14, http://x.org/y.html\n")
    deps.fresh()
    with deps.recording() as touched:
        deps.mentioned(source.relative_to(tmp_path), source.read_text())
        deps.touch("media/missing.png")
    assert set(touched) == {"data/t.csv", "gallery", "media/missing.png"}
    assert touched["media/missing.png"] == "missing"
    assert deps.unchanged(touched)
    # a photo added to the folder, a file appearing, a file edited: changed
    for change in (
        lambda: (tmp_path / "gallery/2.jpg").write_text(""),
        lambda: (tmp_path / "media").mkdir() or (tmp_path / "media/missing.png").write_text(""),
        lambda: os.utime(tmp_path / "data/t.csv", ns=(1, 1)),
    ):
        deps.fresh()
        assert deps.unchanged(touched)
        change()
        deps.fresh()
        assert not deps.unchanged(touched)
        with deps.recording() as touched:
            deps.mentioned(source.relative_to(tmp_path), source.read_text())
            deps.touch("media/missing.png")


def test_touch_outside_a_read_does_nothing():
    deps.touch("x")
