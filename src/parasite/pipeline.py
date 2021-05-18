from __future__ import annotations

import os
from typing import TYPE_CHECKING
from logging import getLogger
import psutil

from urlpath import URL as Url
import defopt
import parsl
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor
# from parsl.executors import HighThroughputExecutor
# from parsl.providers import LocalProvider
from parsl.utils import get_all_checkpoints
from parsl.data_provider.files import File


from .data import Posts, Pages
from .util import TimeElapse
from .helpers import write_tipuesearch, to_feed
from .to_ast import posts_to_index_ast, posts_to_tag_ast, posts_to_archive_ast
from .apps_parsl import app_read_md_to_ast, app_read_md_to_ast_with_teaser, app_post_to_html, app_rsync, app_minify, app_closure_compiler
# require user to put conf.py in cwd
import sys
sys.path.append(os.getcwd())
from conf import PRETTY_URLS, DATE_FORMAT, POSTS, nav_includes, PAGES, header_includes, DEFAULT_LANG, include_after, MATHJAX_CONFIG, search_form, content_footer, BLOG_TITLE, css, include_before, INDEX_TEMPLATE, OUTPUT_DIR, FILES_FOLDERS, CSS, JS, N_JUMBOTRON, N_GRID, INDEX_INCLUDE_JUMBOTRON, TAG_CLOUD_FONT_SIZE_MIN, TAG_CLOUD_FONT_SIZE_MAX, HTML_FILTERS, ROOT_RELATIVE_TO_SEARCH_FORM, LOGO_URL, BLOG_DESCRIPTION, BLOG_AUTHOR, BLOG_EMAIL, SITE_URL, pandoc_input_options, pandoc_output_options, panflute_input_filters, panflute_output_filters, COPYRIGHT, TIMEZONE

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
    timezone: str = r"America/Los_Angeles",
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
            'pandoc_options': pandoc_output_options,
            'css': css,
            'logo_url': Url(LOGO_URL) if LOGO_URL else None,
            'panflute_filters': panflute_output_filters,
            'html_filters': HTML_FILTERS,
        }
        pageses.append(page_class.from_file_system(
            path,
            out_path,
            ext,
            template,
            pretty_urls=pretty_urls,
            date_format=DATE_FORMAT,
            default_lang=DEFAULT_LANG,
            timezone=timezone,
            options=options,
        ))
    return pageses


def main(
    *,
    write_tipuesearch_json: bool = True,
    write_rss: bool = True,
    write_atom: bool = True,
):
    """Parasite static site generator.

    :param bool write_tipuesearch_json: write tipuesearch JSON file.
    """
    time_elapse = TimeElapse()
    if JS:
        minifies_js = [
            app_minify(
                inputs=[File(path) for path in paths],
                outputs=[File(out_path)]
            )
            for out_path, paths in JS.items()
        ]
    if CSS:
        minifies = [
            app_minify(
                inputs=[File(path) for path in paths],
                outputs=[File(out_path)]
            )
            for out_path, paths in CSS.items()
        ]
    if FILES_FOLDERS:
        rsyncs = [
            app_rsync(in_dir, OUTPUT_DIR, out_sub_dir)
            for in_dir, out_sub_dir in FILES_FOLDERS.items()
        ]
    time_elapse.report('staging for minifies and rsync.')

    pages = Pages(sum((pages_.pages for pages_ in get_pages(PAGES, Pages, timezone=TIMEZONE)), []))
    posts = Posts(sum((pages_.pages for pages_ in get_pages(POSTS, Posts, timezone=TIMEZONE)), []))
    time_elapse.report('glob pages/posts from file system.')

    pages_ast_futures = [
        app_read_md_to_ast(
            pandoc_input_options,
            panflute_input_filters,
            inputs=[File(str((page.path)))],
        )
        for page in pages.pages
    ]
    posts_ast_futures = [
        app_read_md_to_ast_with_teaser(
            pandoc_input_options,
            panflute_input_filters,
            inputs=[File(str((page.path)))],
        )
        for page in posts.pages
    ]
    time_elapse.report('staging to get all ASTs.')
    for page, future in zip(pages.pages, pages_ast_futures):
        page.ast = future.result()
    for page, future in zip(posts.pages, posts_ast_futures):
        page.ast, page.teaser = future.result()
    time_elapse.report('got all ASTs.')

    posts.sort()
    time_elapse.report('sorting posts.')
    posts.get_neighbor_urls()
    time_elapse.report('get neighbor urls.')

    all_pages = pages.pages + posts.pages
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
        for page in all_pages
    ]
    time_elapse.report('staging pages/posts HTML output.')

    # cat index
    options = posts.pages[0].options
    for case, dict_ in (
        ('categories', posts.categories),
        ('tags', posts.tags),
    ):
        for name, cat_posts in dict_.items():
            index_ast = posts_to_index_ast(
                cat_posts,
                name,
                n_jumbotron=N_JUMBOTRON,
                n_grid=N_GRID,
                index_include_jumbotron=INDEX_INCLUDE_JUMBOTRON,
                lang=DEFAULT_LANG,
            )
            output_futures.append(app_post_to_html(
                index_ast,
                '../..',
                None,
                None,
                DEFAULT_LANG,
                '.md',
                inputs=[] if INDEX_TEMPLATE is None else [File(str((INDEX_TEMPLATE)))],
                outputs=[File(str((OUTPUT_DIR / 'categories' / (name if case == 'tags' else f'cat_{name}') / 'index.html')))],
                **options,
            ))
    time_elapse.report('staging cat-index.')
    # tags
    _template = posts.pages[0].template
    inputs = [] if _template is None else [File(str((_template)))]
    tag_ast = posts_to_tag_ast(
        posts.categories,
        posts.tags,
        font_size_min=TAG_CLOUD_FONT_SIZE_MIN,
        font_size_max=TAG_CLOUD_FONT_SIZE_MAX,
        root='..',
        lang=DEFAULT_LANG,
    )
    output_futures.append(app_post_to_html(
        tag_ast,
        '..',
        None,
        None,
        DEFAULT_LANG,
        '.md',
        inputs=inputs,
        outputs=[File(str((OUTPUT_DIR / 'categories' / 'index.html')))],
        **options,
    ))
    time_elapse.report('staging tag page.')
    # archive
    archive_ast = posts_to_archive_ast(
        posts.pages,
        root='..',
        lang=DEFAULT_LANG,
    )
    output_futures.append(app_post_to_html(
        archive_ast,
        '..',
        None,
        None,
        DEFAULT_LANG,
        '.md',
        inputs=inputs,
        outputs=[File(str((OUTPUT_DIR / 'archive' / 'index.html')))],
        **options,
    ))
    time_elapse.report('staging archive page.')
    # index
    index_ast = posts_to_index_ast(
        posts.pages,
        BLOG_TITLE[DEFAULT_LANG],
        n_jumbotron=N_JUMBOTRON,
        n_grid=N_GRID,
        index_include_jumbotron=INDEX_INCLUDE_JUMBOTRON,
        lang=DEFAULT_LANG,
    )
    output_futures.append(app_post_to_html(
        index_ast,
        '.',
        None,
        None,
        DEFAULT_LANG,
        '.md',
        inputs=[] if INDEX_TEMPLATE is None else [File(str((INDEX_TEMPLATE)))],
        outputs=[File(str((OUTPUT_DIR / 'index.html')))],
        **options,
    ))
    time_elapse.report('staging index.')
    if write_tipuesearch_json:
        # search: we're not using parsl here, as
        # it needs to be re-generated even if only one page is changed,
        # and the time taken is very small for now.
        # as site gets bigger, may need to cache the Page.text e.g. in app_read_md_to_ast*?
        write_tipuesearch(
            OUTPUT_DIR / 'assets/js/tipuesearch_content.js',
            all_pages,
            root=ROOT_RELATIVE_TO_SEARCH_FORM,
        )
        time_elapse.report('wrote tipuesearch.')

    if write_atom or write_rss:
        to_feed(
            posts.pages,
            BLOG_TITLE[DEFAULT_LANG],
            BLOG_DESCRIPTION[DEFAULT_LANG],
            BLOG_AUTHOR[DEFAULT_LANG],
            BLOG_EMAIL,
            SITE_URL,
            LOGO_URL,
            DEFAULT_LANG,
            COPYRIGHT,
            TIMEZONE,
            output_dir=OUTPUT_DIR,
            write_atom=write_atom,
            write_rss=write_rss,
        )
        time_elapse.report('wrote rss and/or atom feed.')

    for future in output_futures:
        future.result()
    if FILES_FOLDERS:
        for rsync in rsyncs:
            rsync.result()
    if CSS:
        for minify in minifies:
            minify.result()
    if JS:
        for minify in minifies_js:
            minify.result()
    time_elapse.report('collecting all futures.')


def cli():
    defopt.run(main)


if __name__ == "__main__":
    cli()
