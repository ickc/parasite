import os
import tempfile
from pathlib import Path

import pytest

from para.output import Output, place


def test_place_shares_on_one_filesystem(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("a")
    dest = tmp_path / "out" / "a.txt"
    dest.parent.mkdir()
    how = place(src, dest)
    assert how in ("reflink", "link")
    assert dest.read_text() == "a"
    assert dest.stat().st_mtime_ns == src.stat().st_mtime_ns
    assert not [p for p in dest.parent.iterdir() if p.name != "a.txt"]


@pytest.mark.skipif(not os.path.isdir("/dev/shm"), reason="needs another filesystem")
def test_place_copies_across_filesystems(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("a")
    if os.stat("/dev/shm").st_dev == src.stat().st_dev:
        pytest.skip("/dev/shm is on the same filesystem")
    with tempfile.TemporaryDirectory(dir="/dev/shm") as other:
        dest = Path(other) / "a.txt"
        assert place(src, dest) == "copy"
        assert dest.read_text() == "a"


def test_copy_skips_what_is_there(tmp_path: Path) -> None:
    src = tmp_path / "files" / "a.txt"
    src.parent.mkdir()
    src.write_text("a")
    os.utime(src, ns=(10**18, 10**18))
    output = Output(tmp_path / "output")
    dest = tmp_path / "output" / "a.txt"
    assert output.copy(src, dest, "files")
    assert not Output(tmp_path / "output").copy(src, dest, "files")
    # a source replaced (as git or an editor does) is placed again
    new = src.with_name("new")
    new.write_text("b")
    os.replace(new, src)
    assert Output(tmp_path / "output").copy(src, dest, "files")
    assert dest.read_text() == "b"


def test_write_never_writes_through_a_link(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("source")
    dest = tmp_path / "output" / "a.txt"
    dest.parent.mkdir()
    os.link(src, dest)
    Output(tmp_path / "output").write(dest, "page", "a page")
    assert src.read_text() == "source"
    assert dest.read_text() == "page"


def test_claim_tree_pairs(tmp_path: Path) -> None:
    (tmp_path / "files" / "sub").mkdir(parents=True)
    (tmp_path / "files" / "sub" / "b.txt").write_text("b")
    output = Output(tmp_path / "output")
    pairs = output.claim_tree(tmp_path / "files", tmp_path / "output" / "x", "files")
    assert pairs == [(tmp_path / "files" / "sub" / "b.txt", tmp_path / "output" / "x" / "sub" / "b.txt")]
