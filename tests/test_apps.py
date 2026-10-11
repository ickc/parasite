from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from parasite import apps

if TYPE_CHECKING:
    from typing import List

    from parasite.panflute_filters import PanfluteFilter

example_path = Path("docs/README.md")


def panflute_filters(ext: str) -> List[PanfluteFilter]:
    return [lambda x: x]


def pandoc_options(ext: str) -> List[str]:
    return ["--from=markdown"]


@pytest.mark.parametrize(
    "panflute_filters",
    [
        panflute_filters,
        lambda x: [],
    ],
)
def test_read_md_to_ast(panflute_filters):
    """Test app.read_md_to_ast

    We only test it runs ok.
    """
    apps.read_md_to_ast(
        pandoc_options=pandoc_options,
        panflute_filters=panflute_filters,
        inputs=[example_path],
    )



def test_xml_safe():
    assert apps.xml_safe("a\x1b[0;31mred\x1b[0m\x08b\tc\n") == "aredb\tc\n"
    assert apps.xml_safe("<style scoped>x</style>") == "<style>x</style>"


def test_mathjax_bold_ell():
    import panflute as pf

    from parasite.panflute_filters import mathjax_bold_ell_filter

    doc = pf.Doc(pf.Para(pf.Math(r"\mathbf{\ell} + \mathbf{\hat{\ell}} + \mathbf{\hat{x}}", format="InlineMath")))
    doc = mathjax_bold_ell_filter(doc)
    assert doc.content[0].content[0].text == r"\pmb{\ell} + \pmb{\hat{\ell}} + \mathbf{\hat{x}}"
