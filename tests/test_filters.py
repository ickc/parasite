from __future__ import annotations

import panflute as pf
import pytest

from para import filters as F
from para.filters import Filter, FilterError, chosen, document_choice, run
from para.settings import load

ALLOW = {
    "a": Filter("a", python="para.panflute_filters:mathjax_bold_ell_filter", default=True),
    "b": Filter("b", python="para.panflute_filters:mathjax_bold_ell_filter"),
    "c": Filter("c", python="para.panflute_filters:mathjax_bold_ell_filter", at="render"),
    "n": Filter("n", python="para.panflute_filters:mathjax_bold_ell_filter", default=True, inputs=("ipynb",)),
}


def test_document_choice():
    assert document_choice(["b", "-a"], ALLOW, "x.md") == ({"b"}, {"a"})
    with pytest.raises(FilterError, match="add it to the site"):
        document_choice(["nope"], ALLOW, "x.md")
    with pytest.raises(FilterError, match="a path is not allowed"):
        document_choice(["filters/x.lua"], ALLOW, "x.md")


def test_chosen_in_the_allow_lists_order():
    names = lambda fs: [f.name for f in fs]  # noqa: E731
    assert names(chosen(ALLOW, "read", None, "x.md", ext=".md")) == ["a"]
    assert names(chosen(ALLOW, "read", ["b"], "x.md", ext=".md")) == ["a", "b"]
    assert names(chosen(ALLOW, "read", ["b", "-a"], "x.md", ext=".ipynb")) == ["b", "n"]
    assert names(chosen(ALLOW, "render", None, "x.md")) == []
    assert names(chosen(ALLOW, "render", ["c"], "x.md")) == ["c"]
    assert names(chosen(ALLOW, "render", ["-c"], "x.md", profile=["c"])) == []


def test_specs():
    assert Filter.from_spec("t", {"lua": "t", "at": "render"}).at == "render"
    for spec, message in (({}, "one of"), ({"wasm": "x"}, "not supported"), ({"python": "m:f", "at": "x"}, "at =")):
        with pytest.raises(FilterError, match=message):
            Filter.from_spec("t", spec)
    with pytest.raises(FilterError, match="not a path"):
        F.find_lua("../x.lua")


@pytest.fixture
def lua_dir(tmp_path, monkeypatch):
    folder = tmp_path / "installed"
    folder.mkdir()
    (folder / "upper.lua").write_text("function Str(s) return pandoc.Str(s.text:upper()) end\n")
    (folder / "fmt.lua").write_text('function Str(s) if s.text == "FMT" then return pandoc.Str(FORMAT) end end\n')
    monkeypatch.setattr(F, "lua_dirs", lambda: (folder,))
    return folder


def test_lua_and_python(lua_dir):
    doc = pf.Doc(pf.Para(pf.Str("x"), pf.Space(), pf.Math(r"\mathbf{\ell}", format="InlineMath")))
    chain = [Filter("u", lua="upper"), Filter("m", python="para.panflute_filters:mathjax_bold_ell_filter")]
    doc = run(chain, doc)
    assert pf.stringify(doc.content[0].content[0]) == "X"
    assert doc.content[0].content[2].text == r"\pmb{\ell}"


def test_a_documents_lua_render_filter_sees_its_format(lua_dir, tmp_path, monkeypatch):
    site = tmp_path / "site"
    (site / "pages").mkdir(parents=True)
    monkeypatch.chdir(site)
    (site / "parasite.toml").write_text(
        '[site]\nurl = "https://example.org/"\n[files]\n[search]\nenabled = false\n[check]\nlinks = false\n'
        '[filters.fmt]\nlua = "fmt"\nat = "render"\n'
    )
    (site / "pages/a.md").write_text("---\ntitle: A\nfilters: [fmt]\n---\n\nFMT\n")
    (site / "pages/b.md").write_text("---\ntitle: B\n---\n\nFMT\n")
    load(site / "parasite.toml")().exec()
    assert "<p>html</p>" in (site / "output/a/index.html").read_text()
    assert "<p>FMT</p>" in (site / "output/b/index.html").read_text()
