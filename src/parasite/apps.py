"""Some functions for pipelines

all functions should be imported inside functions for parsl
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from datetime import datetime

import panflute
from parsl import python_app
from parsl.dataflow.memoization import id_for_memo

if TYPE_CHECKING:
    from typing import Optional, List


def read_md_to_ast(path: Path, mtime: Optional[datetime] = None) -> panflute.elements.Doc:
    """Read from markdown to panflute AST

    :param datetime mtime: modification time of the file at path.
    Specified such that update cache only if this is changed.
    """
    from panflute.tools import convert_text

    with open(path, 'r') as f:
        return convert_text(f.read(), standalone=True)


def post_to_html(
    ast: panflute.elements.Doc,
    out_path: Path,
    template: Path,
    tags: List[str],
    tags_counts: List[int],
    prev_url: Path,
    next_url: Path,
    header_includes: str = '',
    include_before: str = '',
    include_after: str = '',
    pandoc_options: List[str] = [],
    output_dir: Path = Path('output'),
):
    """
    warning: AST is currently mutated
    """
    # TODO: inject tags+counts, prev/next_url
    # either by manipulating the string here
    # or set metadata variable and let pandoc template handles it
    ast.metadata['header-includes'] = panflute.RawBlock(header_includes)
    ast.metadata['include-before'] = panflute.RawBlock(include_before)
    ast.metadata['include-after'] = panflute.RawBlock(include_after)

    other_options = [
        f'--output={Path(output_dir) / out_path}',
        f'--template={template}',
    ]

    panflute.tools.convert_text(ast, input_format='panflute', output_format='html', standalone=True, extra_args=pandoc_options + other_options)


@id_for_memo.register(Path)
def id_for_memo_path(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo(str(path))


@id_for_memo.register(datetime)
def id_for_memo_datetime(time: datetime, output_ref: bool = False) -> bytes:
    return id_for_memo(str(time))


@id_for_memo.register(panflute.elements.Doc)
def id_for_memo_doc(doc: panflute.elements.Doc, output_ref: bool = False) -> bytes:
    return id_for_memo(doc.to_json())


app_read_md_to_ast = python_app(read_md_to_ast, cache=True)
app_post_to_html = python_app(post_to_html, cache=True)
