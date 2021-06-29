from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from panflute.tools import convert_text

from parasite import apps

if TYPE_CHECKING:
    from typing import Callable, List

example_path = Path('docs/README.md')


def panflute_filters(ext: str) -> List[Callable]:
    return [lambda x, y: None]


def pandoc_options(ext: str) -> List[str]:
    return ['--from=markdown']


@pytest.mark.parametrize(
    "panflute_filters",
    [
        panflute_filters,
        lambda x: None,
    ]
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


def test_get_teaser():
    doc = convert_text("""Some post

-   with some contents

<!--more-->

-   with more contents""", standalone=True)
    content = apps.get_teaser(doc)
    output = convert_text(content, input_format='panflute', output_format='markdown')
    assert output == """Some post

-   with some contents"""
