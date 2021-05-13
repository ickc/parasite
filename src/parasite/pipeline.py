from __future__ import annotations

from typing import TYPE_CHECKING
from logging import getLogger

import parsl
from parsl.configs.local_threads import config
from parsl.utils import get_all_checkpoints


from .data import Posts, Pages
from .apps import posts_to_index_ast, app_read_md_to_ast, app_read_md_to_ast_with_teaser, app_post_to_html, InputPath
# require user to put conf.py in cwd
# from conf import *
from .conf import PRETTY_URLS, DATE_FORMAT, POSTS, nav_includes, PAGES, header_includes, DEFAULT_LANG, include_after, MATHJAX_CONFIG, search_form, content_footer, pandoc_options, BLOG_TITLE, css, include_before, INDEX_TEMPLATE

if TYPE_CHECKING:
    from typing import Optional, Tuple, List

config.checkpoint_mode = 'task_exit'
config.checkpoint_files = get_all_checkpoints()
parsl.load(config)

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
    pages = Pages(sum((pages_.pages for pages_ in get_pages(PAGES, Pages)), []))
    logger.info(f'Obtaining {pages.dataframe}')
    posts = Posts(sum((pages_.pages for pages_ in get_pages(POSTS, Posts)), []))
    logger.info(f'Obtaining {posts.dataframe}')

    logger.info('Get all ASTs.')
    pages_ast_futures = [app_read_md_to_ast(page.path) for page in pages.pages]
    posts_ast_futures = [app_read_md_to_ast_with_teaser(page.path) for page in posts.pages]
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
            page.out_path,
            page.root,
            page.template,
            page.prev,
            page.next,
            page.lang,
            page.ext,
            **page.options,
        )
        for page in pages.pages + posts.pages
    ]
    # tags
    template = posts.pages[0].template
    options = posts.pages[0].options
    output_futures.append(app_post_to_html(
        posts.tag_ast(),
        'categories/index.html',
        '..',
        template,
        None,
        None,
        'en',
        '.md',
        **options,
    ))
    # archive
    output_futures.append(app_post_to_html(
        posts.archive_ast,
        'archive/index.html',
        '..',
        template,
        None,
        None,
        'en',
        '.md',
        **options,
    ))
    # index
    index_ast = posts_to_index_ast(
        posts.pages,
        BLOG_TITLE['en'],
    )
    output_futures.append(app_post_to_html(
        index_ast,
        'index.html',
        '.',
        None if INDEX_TEMPLATE is None else InputPath(INDEX_TEMPLATE),
        None,
        None,
        'en',
        '.md',
        **options,
    ))
    for future in output_futures:
        future.result()


if __name__ == "__main__":
    main()
