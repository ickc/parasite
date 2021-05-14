"""wrapping apps to parsl apps

all functions should be imported inside functions for parsl
"""
from __future__ import annotations

from parsl import python_app, bash_app


@python_app(cache=True)
def app_read_md_to_ast(inputs=[]):
    from pathlib import Path

    from .apps import read_md_to_ast

    input_paths = [Path(file.filepath) for file in inputs]
    return read_md_to_ast(input_paths)


@python_app(cache=True)
def app_read_md_to_ast_with_teaser(inputs=[]):
    from pathlib import Path

    from .apps import read_md_to_ast_with_teaser

    input_paths = [Path(file.filepath) for file in inputs]
    return read_md_to_ast_with_teaser(input_paths)


@python_app(cache=True)
def app_post_to_html(
    ast,
    root,
    prev,
    next,
    lang,
    ext,
    inputs=[],   # template
    outputs=[],  # out_path
    header_includes=None,
    include_before=None,
    include_after=None,
    mathjax_config=None,
    search_form=None,
    content_footer=None,
    blog_title=None,
    nav=None,
    pandoc_options=None,
    css=None,
):
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
        header_includes=header_includes,
        include_before=include_before,
        include_after=include_after,
        mathjax_config=mathjax_config,
        search_form=search_form,
        content_footer=content_footer,
        blog_title=blog_title,
        nav=nav,
        pandoc_options=pandoc_options,
        css=css,
    )


@bash_app
def app_rsync(in_dir: str, out_base_dir: str, out_sub_dir: str) -> str:
    from pathlib import Path

    out_dir = Path(out_base_dir) / out_sub_dir
    out_dir.mkdir(exist_ok=True, parents=True)
    return f'rsync -a {in_dir}/ {out_dir}/'


@bash_app
def app_minify(inputs=[], outputs=[], format: str = 'css'):
    '''minify using the Go minifier

    https://github.com/tdewolff/minify/tree/master/cmd/minify
    '''
    from pathlib import Path

    input_paths = [file.filepath for file in inputs]
    output_path = Path(outputs[0].filepath)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    return f'cat {" ".join(input_paths)} | minify --type {format} -o {output_path}'


@bash_app
def app_closure_compiler(inputs=[], outputs=[]):
    from pathlib import Path

    input_paths = [file.filepath for file in inputs]
    output_path = Path(outputs[0].filepath)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    return f'closure-compiler -O SIMPLE --js {" ".join(input_paths)} --js_output_file {output_path} -W QUIET --jscomp_off=checkVars'


@bash_app
def app_cat(inputs=[], outputs=[]):
    from pathlib import Path

    input_paths = [file.filepath for file in inputs]
    output_path = Path(outputs[0].filepath)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    return f'cat {" ".join(input_paths)} > {output_path}'


import os
from pathlib import Path
from logging import getLogger

from parsl.dataflow.memoization import id_for_memo
from parsl.data_provider.files import File

import panflute as pf

logger = getLogger('parasite')


@id_for_memo.register(pf.elements.Doc)
def id_for_memo_doc(doc: pf.elements.Doc, output_ref: bool = False) -> bytes:
    return id_for_memo(doc.to_json())


@id_for_memo.register(Path)
def id_for_memo_path(path: Path, output_ref: bool = False) -> bytes:
    return id_for_memo(str(path))


@id_for_memo.register(File)
def id_for_memo_File(f: File, output_ref: bool = False) -> bytes:
    if output_ref:
        logger.debug("hashing File as output ref without content: {}".format(f))
        return id_for_memo(f.url)
    else:
        logger.debug("hashing File as input with content: {}".format(f))
        assert f.scheme == "file"
        filename = f.filepath
        stat_result = os.stat(filename)

        return id_for_memo([f.url, stat_result.st_size, stat_result.st_mtime])
