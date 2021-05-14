from __future__ import annotations

import os
from typing import TYPE_CHECKING
from logging import getLogger
import psutil
from pathlib import Path

import parsl
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor
from parsl.executors import HighThroughputExecutor
from parsl.providers import LocalProvider
from parsl.utils import get_all_checkpoints
from parsl.data_provider.files import File


from .data import Posts, Pages
from .to_ast import posts_to_index_ast
from .apps_parsl import app_read_md_to_ast, app_read_md_to_ast_with_teaser, app_post_to_html, app_rsync, app_minify, app_cat
# require user to put conf.py in cwd
import sys
sys.path.append(os.getcwd())
from conf import PRETTY_URLS, DATE_FORMAT, POSTS, nav_includes, PAGES, header_includes, DEFAULT_LANG, include_after, MATHJAX_CONFIG, search_form, content_footer, pandoc_options, BLOG_TITLE, css, include_before, INDEX_TEMPLATE, OUTPUT_DIR, FILES_FOLDERS, CSS, JS

if TYPE_CHECKING:
    from typing import Optional, Tuple, List

executor = ThreadPoolExecutor(
    max_threads=psutil.cpu_count(logical=False),
    working_dir=os.getcwd(),
)
# executor = HighThroughputExecutor(
#     provider=LocalProvider(
#         worker_init=f". {os.path.expanduser('~/.mambaforge/envs/all39-defaults/bin/activate')}",
#     ),
#     cores_per_worker=1,
# )
parsl.load(Config(
    executors=[executor],
    checkpoint_mode='task_exit',
    checkpoint_files=get_all_checkpoints(),
))

# parsl.set_stream_logger()
logger = getLogger('parasite')


def get_pages(
    PAGES: Tuple[
        Tuple[
            str,           # in-dir
            str,           # out-dir
            str,           # ext
            Optional[str]  # template
        ],
        ...
    ],
    page_class,
) -> List[Pages]:
    pageses = []
    for path, out_path, ext, template in PAGES:
        pretty_urls = PRETTY_URLS[ext]
        DATE_FORMAT
        options = {
            'header_includes': header_includes,
            'include_before': include_before,
            'include_after': include_after,
            'mathjax_config': MATHJAX_CONFIG,
            'search_form': search_form,
            'content_footer': content_footer,
            'blog_title': BLOG_TITLE,
            'nav': nav_includes,
            'pandoc_options': pandoc_options,
            'css': css,
        }
        pageses.append(page_class.from_file_system(
            path,
            out_path,
            ext,
            template,
            pretty_urls=pretty_urls,
            date_format=DATE_FORMAT,
            default_lang=DEFAULT_LANG,
            options=options,
        ))
    return pageses


def main():
    if CSS:
        minifies = [
            app_minify(
                inputs=[File(path) for path in paths],
                outputs=[File(out_path)]
            )
            for out_path, paths in CSS.items()
        ]
    if JS:
        minifies_js = [
            app_cat(
                inputs=[File(path) for path in paths],
                outputs=[File(out_path)]
            )
            for out_path, paths in JS.items()
        ]
    if FILES_FOLDERS:
        rsyncs = [
            app_rsync(in_dir, OUTPUT_DIR, out_sub_dir)
            for in_dir, out_sub_dir in FILES_FOLDERS.items()
        ]

    pages = Pages(sum((pages_.pages for pages_ in get_pages(PAGES, Pages)), []))
    logger.info(f'Obtaining {pages.dataframe}')
    posts = Posts(sum((pages_.pages for pages_ in get_pages(POSTS, Posts)), []))
    logger.info(f'Obtaining {posts.dataframe}')

    logger.info('Get all ASTs.')
    pages_ast_futures = [app_read_md_to_ast(inputs=[File(str((page.path)))]) for page in pages.pages]
    posts_ast_futures = [app_read_md_to_ast_with_teaser(inputs=[File(str((page.path)))]) for page in posts.pages]
    for page, future in zip(pages.pages, pages_ast_futures):
        page.ast = future.result()
    for page, future in zip(posts.pages, posts_ast_futures):
        page.ast, page.teaser = future.result()
    logger.info('Got all ASTs.')

    posts.sort()
    posts.get_neighbor_urls()

    output_futures = [
        app_post_to_html(
            page.ast,
            page.root,
            page.prev,
            page.next,
            page.lang,
            page.ext,
            inputs=[] if page.template is None else [File(str((page.template)))],
            outputs=[File(str((OUTPUT_DIR / page.out_path)))],
            **page.options,
        )
        for page in pages.pages + posts.pages
    ]
    # tags
    _template = posts.pages[0].template
    inputs = [] if _template is None else [File(str((_template)))]
    options = posts.pages[0].options
    output_futures.append(app_post_to_html(
        posts.tag_ast(),
        '..',
        None,
        None,
        'en',
        '.md',
        inputs=inputs,
        outputs=[File(str((OUTPUT_DIR / 'categories' / 'index.html')))],
        **options,
    ))
    # archive
    output_futures.append(app_post_to_html(
        posts.archive_ast,
        '..',
        None,
        None,
        'en',
        '.md',
        inputs=inputs,
        outputs=[File(str((OUTPUT_DIR / 'archive' / 'index.html')))],
        **options,
    ))
    # index
    index_ast = posts_to_index_ast(
        posts.pages,
        BLOG_TITLE['en'],
    )
    output_futures.append(app_post_to_html(
        index_ast,
        '.',
        None,
        None,
        'en',
        '.md',
        inputs=[] if INDEX_TEMPLATE is None else [File(str((INDEX_TEMPLATE)))],
        outputs=[File(str((OUTPUT_DIR / 'index.html')))],
        **options,
    ))
    for future in output_futures:
        future.result()
    if FILES_FOLDERS:
        for rsync in rsyncs:
            rsync.result()
    if JS:
        for minify in minifies_js:
            minify.result()
    if CSS:
        for minify in minifies:
            minify.result()


if __name__ == "__main__":
    main()
