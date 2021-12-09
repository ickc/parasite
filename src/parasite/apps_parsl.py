"""Wrapping apps to parsl apps.

all functions should be imported inside functions for parsl.

We're not running unit tests for anything defined here,
as they should be thin wrappers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from parsl import bash_app, python_app

if TYPE_CHECKING:
    from typing import Callable, Dict, List, Optional, Tuple, Union

    from panflute import Doc, Element
    from parsl.data_provider.files import File
    from urlpath import URL as Url

    from .panflute_filters import PANFLUTE_ACTION


@python_app(cache=True)
def app_read_md_to_ast(
    pandoc_options: Callable[[str], List[str]],
    panflute_filters: Callable[[str], List[PANFLUTE_ACTION]],
    inputs: list[File] = [],
) -> pf.elements.Doc:
    from pathlib import Path

    from .apps import read_md_to_ast

    input_paths = [Path(file.filepath) for file in inputs]
    return read_md_to_ast(
        pandoc_options,
        panflute_filters,
        inputs=input_paths,
    )


@python_app(cache=True)
def app_read_md_to_ast_with_teaser(
    pandoc_options: Callable[[str], List[str]],
    panflute_filters: Callable[[str], List[PANFLUTE_ACTION]],
    inputs: List[File] = [],
) -> Tuple[pf.elements.Doc, pf.containers.ListContainer]:
    from pathlib import Path

    from .apps import read_md_to_ast_with_teaser

    input_paths = [Path(file.filepath) for file in inputs]
    return read_md_to_ast_with_teaser(
        pandoc_options,
        panflute_filters,
        inputs=input_paths,
    )


@python_app(cache=True)
def app_post_to_html(
    ast: pf.elements.Doc,
    root: str,
    prev: Optional[Tuple[Url, Optional[str]]],
    next: Optional[Tuple[Url, Optional[str]]],
    lang: str,
    ext: str,
    /,
    *,
    inputs: List[File] = [],  # template
    outputs: List[File] = [],  # out_path
    show_previewimage_in_post: bool = True,
    header_includes: Callable[[str, str, str], str],
    include_before: Callable[[str, str, str], str],
    include_after: Callable[[str, str, str], str],
    script_include_after: Callable[[str, str], str],
    pandoc_options: Callable[[str, str], List[str]],
    panflute_filters: Callable[[str, str], List[PANFLUTE_ACTION]],
    js: Callable[[str, str], List[str]],
    css: Callable[[str, str], List[str]],
    mathjax_config: str = "",
    search_form: Optional[Callable[[str, str, str], str]] = None,
    content_footer: Optional[Callable[[str, str, str], str]] = None,
    blog_title: Dict[str, str] = {},
    nav: Optional[Callable[[str, str, str], str]] = None,
    logo_url: Optional[Url] = None,
    html_filters: List[Callable[[str], str]] = [],
) -> None:
    from pathlib import Path

    from .apps import post_to_html

    input_paths = [Path(file.filepath) for file in inputs]
    output_paths = [Path(file.filepath) for file in outputs]
    return post_to_html(
        ast,
        root,
        prev,
        next,
        lang,
        ext,
        inputs=input_paths,
        outputs=output_paths,
        show_previewimage_in_post=show_previewimage_in_post,
        header_includes=header_includes,
        include_before=include_before,
        include_after=include_after,
        script_include_after=script_include_after,
        pandoc_options=pandoc_options,
        panflute_filters=panflute_filters,
        js=js,
        css=css,
        mathjax_config=mathjax_config,
        search_form=search_form,
        content_footer=content_footer,
        blog_title=blog_title,
        nav=nav,
        logo_url=logo_url,
        html_filters=html_filters,
    )


@bash_app
def app_rsync(in_dir: str, out_base_dir: str, out_sub_dir: str) -> str:
    from pathlib import Path

    out_dir = Path(out_base_dir) / out_sub_dir
    out_dir.mkdir(exist_ok=True, parents=True)
    return f"rsync -a {in_dir}/ {out_dir}/"


@bash_app
def app_minify(inputs: list[File] = [], outputs: list[File] = []) -> str:
    """minify using the Go minifier

    https://github.com/tdewolff/minify/tree/master/cmd/minify
    """
    from pathlib import Path

    input_paths = [file.filepath for file in inputs]
    output_path = Path(outputs[0].filepath)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    return (
        f"minify --type {output_path.suffix[1:]} -b -o"
        f' {output_path} {" ".join(input_paths)}'
    )


@bash_app
def app_closure_compiler(inputs: list[File] = [], outputs: list[File] = []) -> str:
    from pathlib import Path

    input_paths = [file.filepath for file in inputs]
    output_path = Path(outputs[0].filepath)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    return (
        f'closure-compiler -O SIMPLE --js {" ".join(input_paths)} --js_output_file'
        f" {output_path} -W QUIET --jscomp_off=checkVars"
    )


import os
from logging import getLogger
from pathlib import Path

import panflute as pf
from parsl.data_provider.files import File
from parsl.dataflow.memoization import id_for_memo
from urlpath import URL as Url

logger = getLogger(__name__)


@id_for_memo.register(pf.elements.Doc)
def id_for_memo_doc(doc: pf.elements.Doc, output_ref: bool = False) -> bytes:
    return id_for_memo(doc.to_json())


@id_for_memo.register(Path)
def id_for_memo_path(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo(str(path))


@id_for_memo.register(Url)
def id_for_memo_url(url: Url, output_ref: bool = False) -> bytes:
    return id_for_memo(str(url))


@id_for_memo.register(File)
def id_for_memo_File(f: File, output_ref: bool = False) -> bytes:
    if output_ref:
        logger.debug("hashing File as output ref without content: {}".format(f))
        return id_for_memo(f.url)
    else:
        logger.debug("hashing File as input with content: {}".format(f))
        if f.scheme != "file":
            raise TypeError(f'{f} has a scheme {f.scheme} different from "file".')
        filename = f.filepath
        stat_result = os.stat(filename)

        return id_for_memo([f.url, stat_result.st_size, stat_result.st_mtime])
