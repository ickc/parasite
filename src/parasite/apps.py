"""Some functions for pipelines

all functions should be imported inside functions for parsl
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from datetime import datetime
import os

import panflute
from parsl import python_app
from parsl.dataflow.memoization import id_for_memo

if TYPE_CHECKING:
    from typing import Optional, List


# doesn't work: https://bugs.python.org/issue24132
# class InputPath(Path):
#     pass

class InputPath:

    def __init__(self, path: str):
        self.path = Path(path)

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return repr(self.path)

    def __truediv__(self, other):
        return self.path / other


def read_md_to_ast(path: InputPath) -> panflute.elements.Doc:
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
    url: Path,
    template: InputPath,
    tags: List[str],
    tags_counts: List[int],
    prev_url: Optional[Path],
    next_url: Optional[Path],
    header_includes: str = '',
    include_before: str = '',
    include_after: str = '',
    mathjax_config: str = '',
    search_form: str = '',
    content_footer: str = '',
    blog_title: str = '',
    pandoc_options: List[str] = [],
    output_dir: Path = Path('output'),
):
    """
    warning: AST is currently mutated
    """
    # TODO: inject tags+counts, prev/next_url
    # either by manipulating the string here
    # or set metadata variable and let pandoc template handles it
    # neighbor_links = []
    # if prev_url is not None:
    #     prev_url_rel = os.path.relpath(prev_url, url)
    #     neighbor_links.append(f'<link rel="prev" href="{prev_url_rel}" type="text/html">')
    # if next_url is not None:
    #     next_url_rel = os.path.relpath(next_url, url)
    #     neighbor_links.append(f'<link rel="next" href="{next_url_rel}" type="text/html">')


    ast.metadata['header-includes'] = panflute.RawBlock(header_includes)
    ast.metadata['include-before'] = panflute.RawBlock(include_before)
    ast.metadata['include-after'] = panflute.RawBlock(include_after)
    if content_footer:
        ast.metadata['content-footer'] = panflute.RawBlock(content_footer)
    if mathjax_config:
        ast.metadata['mathjax-config'] = panflute.RawBlock(mathjax_config)
    if search_form:
        ast.metadata['search-form'] = panflute.RawBlock(search_form)
    if blog_title:
        ast.metadata['title-prefix'] = panflute.RawBlock(blog_title)
    if prev_url is not None:
        ast.metadata['prev-url'] = os.path.relpath(prev_url, url)
    if next_url is not None:
        ast.metadata['next-url'] = os.path.relpath(next_url, url)

    other_options = [
        f'--output={Path(output_dir) / out_path}',
        f'--template={template}',
    ]

    panflute.tools.convert_text(ast, input_format='panflute', output_format='html', standalone=True, extra_args=pandoc_options + other_options)


@id_for_memo.register(Path)
def id_for_memo_path(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo(str(path))


@id_for_memo.register(InputPath)
def id_for_memo_inputpath(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo((str(path), os.path.getmtime(str(path))))


@id_for_memo.register(panflute.elements.Doc)
def id_for_memo_doc(doc: panflute.elements.Doc, output_ref: bool = False) -> bytes:
    return id_for_memo(doc.to_json())


app_read_md_to_ast = python_app(read_md_to_ast, cache=True)
app_post_to_html = python_app(post_to_html, cache=True)
