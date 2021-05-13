"""Some functions for pipelines

all functions should be imported inside functions for parsl
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
import os

import panflute as pf
from panflute.tools import convert_text
from parsl import python_app
from parsl.dataflow.memoization import id_for_memo

if TYPE_CHECKING:
    from typing import Optional, List, Tuple
    from .data import Post

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


def read_md_to_ast(path: InputPath) -> pf.elements.Doc:
    """Read from markdown to panflute AST
    """
    with open(path, 'r') as f:
        return convert_text(f.read(), standalone=True)


def get_teaser(doc: pf.elements.Doc) -> pf.containers.ListContainer:
    content = doc.content
    for i, item in enumerate(content):
        if (type(item) == pf.RawBlock) and (item.text == '<!-- more -->'):
            break
    return content[:i]


def read_md_to_ast_with_teaser(path: InputPath) -> Tuple[pf.elements.Doc, pf.containers.ListContainer]:
    ast = read_md_to_ast(path)
    teaser = get_teaser(ast)
    return ast, teaser


def post_to_html(
    ast: pf.elements.Doc,
    out_path: Path,
    root: str,
    template: Optional[InputPath],
    prev: Optional[Tuple[Path, Optional[str]]],
    next: Optional[Tuple[Path, Optional[str]]],
    header_includes: str = '',
    include_before: str = '',
    include_after: str = '',
    mathjax_config: str = '',
    search_form: str = '',
    content_footer: str = '',
    blog_title: str = '',
    nav: str = '',
    pandoc_options: List[str] = [],
    css: List[str] = [],
    output_dir: Path = Path('output'),
):
    """
    warning: AST is currently mutated
    """
    ast.metadata['header-includes'] = pf.RawBlock(header_includes.format(root=root))
    ast.metadata['include-before'] = pf.RawBlock(include_before)
    ast.metadata['include-after'] = pf.RawBlock(include_after)
    if content_footer:
        ast.metadata['content-footer'] = pf.RawBlock(content_footer)
    if mathjax_config:
        ast.metadata['mathjax-config'] = pf.RawBlock(mathjax_config)
    if search_form:
        ast.metadata['search-form'] = pf.RawBlock(search_form.format(root=root))
    if blog_title:
        ast.metadata['title-prefix'] = pf.RawBlock(blog_title)
    if nav:
        ast.metadata['nav'] = pf.RawBlock(nav.format(root=root))
    if root:
        ast.metadata['root'] = root
    if prev is not None:
        ast.metadata['prev-url'] = str(root / prev[0])
        title = prev[1]
        if title is not None:
            ast.metadata['prev-title'] = title
    if next is not None:
        ast.metadata['next-url'] = str(root / next[0])
        title = next[1]
        if title is not None:
            ast.metadata['next-title'] = title

    css_options = [f"--css={root + c if c.startswith('/') else c}" for c in css]

    out_file = Path(output_dir) / out_path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    other_options = [f'--output={out_file}']
    if template is not None:
        other_options.append(f'--template={template}')

    convert_text(ast, input_format='panflute', output_format='html', standalone=True, extra_args=pandoc_options + css_options + other_options)


def posts_to_index_ast(
    posts: List[Post],
    title: str,
    n_jumbotron: int = 1,
    n_grid: int = 2,
    index_include_jumbotron: bool = True,
) -> pf.elements.Doc:

    def post_to_dict(post: Post) -> dict:
        res = {
            'url': str(post.url),
            'teaser': pf.MetaBlocks(*post.teaser),
        }
        if post.title is not None:
            res['title'] = post.title
        if post.previewimage is not None:
            res['previewimage'] = post.previewimage
        if post.author is not None:
            res['author'] = post.author
        if post.date is not None:
            res['date'] = post.date
        return res

    meta = {
        'title': title,
    }

    temp_index = []
    temp = []
    for post in posts[:n_jumbotron]:
        data = post_to_dict(post)
        temp.append(data)
        if index_include_jumbotron:
            temp_index.append(data)
    meta['index_jumbotron'] = temp

    temp = []
    for post in posts[n_jumbotron:n_jumbotron + n_grid]:
        data = post_to_dict(post)
        temp.append(data)
        if index_include_jumbotron:
            temp_index.append(data)
    meta['index_grid'] = temp

    for post in posts[n_jumbotron + n_grid:]:
        temp_index.append(post_to_dict(post))
    meta['index'] = temp_index

    return pf.elements.Doc(metadata=meta)


@id_for_memo.register(Path)
def id_for_memo_path(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo(str(path))


@id_for_memo.register(InputPath)
def id_for_memo_inputpath(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo((str(path), os.path.getmtime(str(path))))


@id_for_memo.register(pf.elements.Doc)
def id_for_memo_doc(doc: pf.elements.Doc, output_ref: bool = False) -> bytes:
    return id_for_memo(doc.to_json())


app_read_md_to_ast = python_app(read_md_to_ast, cache=True)
app_read_md_to_ast_with_teaser = python_app(read_md_to_ast_with_teaser, cache=True)
app_post_to_html = python_app(post_to_html, cache=True)
