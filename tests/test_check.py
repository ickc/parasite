from __future__ import annotations

import shutil

import pytest

from para.check import check_links

pytestmark = pytest.mark.skipif(shutil.which("lychee") is None, reason="lychee is not installed")


def test_check_links(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.png").write_bytes(b"")
    (tmp_path / "a" / "index.html").write_text(
        '<html><body><img src="x.png"><a href="../b/">b</a><img src="y.png">'
        '<a href="https://example.invalid/">out</a><style>div { background: url(z.svg); }</style></body></html>'
    )
    assert check_links(tmp_path) == 3
    assert check_links(tmp_path, exclude=[r"/b/?$"]) == 2
    assert check_links(tmp_path, exclude_path=["index"]) == 0
