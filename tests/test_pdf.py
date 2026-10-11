"""A PDF profile (Typst), built end to end."""

from __future__ import annotations

import shutil
import struct
import zlib

import pytest

from para.settings import load

pytestmark = pytest.mark.skipif(shutil.which("typst") is None, reason="typst is not installed")


def png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 4 for _ in range(4))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "parasite.toml").write_text(
        '[site]\nurl = "https://example.org/"\ntitle = "T"\n[files]\n[search]\nenabled = false\n[check]\nlinks = false\n'
    )
    (tmp_path / "media").mkdir()
    (tmp_path / "media/a.png").write_bytes(png())
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts/a.md").write_text(
        "---\ntitle: A\ndate: 2020-01-01\nformat:\n  html: default\n  pdf:\n    variables:\n      papersize: a5\n"
        "format-links: [pdf]\n---\n\n# One\n\n$x^2$ and ![a plot](../media/a.png)\n"
    )
    config = load(tmp_path / "parasite.toml")
    config().exec()
    pdf = tmp_path / "output/a/index.pdf"
    first = pdf.read_bytes()
    assert first.startswith(b"%PDF") and b"/Subtype/Image" in first.replace(b" ", b"")
    assert '<a href="index.pdf">PDF</a>' in (tmp_path / "output/a/index.html").read_text()
    # dated by the page, not the clock: a full build gives the same bytes
    shutil.rmtree(tmp_path / ".para")
    pdf.unlink()
    config().exec()
    assert pdf.read_bytes() == first
