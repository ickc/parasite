from __future__ import annotations

import os
from logging import getLogger
from typing import TYPE_CHECKING, Union

import defopt
import parsl
import psutil
from parsl.config import Config as ParslConfig
from parsl.data_provider.files import File
from parsl.executors import ThreadPoolExecutor
# from parsl.executors import HighThroughputExecutor
# from parsl.providers import LocalProvider
from parsl.utils import get_all_checkpoints
from urlpath import URL as Url

from .apps_parsl import app_minify, app_post_to_html, app_read_md_to_ast, app_read_md_to_ast_with_teaser, app_rsync
from .config import Config
from .data import Pages, Posts
from .helpers import to_feed, to_sitemap, write_tipuesearch
from .live import live
from .to_ast import posts_to_archive_ast, posts_to_index_ast, posts_to_tag_ast
from .util import TimeElapse, setup_logging

if TYPE_CHECKING:
    from pathlib import Path
    from typing import List, Optional, Tuple

    from .data import Page, Post

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
parsl.load(
    ParslConfig(
        executors=[executor],
        checkpoint_mode="task_exit",
        checkpoint_files=get_all_checkpoints(),
    )
)

# parsl.set_stream_logger()
setup_logging()
logger = getLogger(__name__)


def _get_pages(
    page_class,
    PAGES: Tuple[
        Tuple[
            str,  # in-dir
            str,  # out-dir
            str,  # ext
            Optional[Path],  # template
        ],
        ...,
    ],
    config: Config,
    timezone: str = r"America/Los_Angeles",
) -> list:
    pageses = []
    for path, out_path, ext, template in PAGES:
        pretty_urls = config.pretty_urls[ext]
        options = {
            "show_previewimage_in_post": config.show_previewimage_in_post,
            "header_includes": config.header_includes,
            "include_before": config.include_before,
            "include_after": config.include_after,
            "script_include_after": config.script_include_after,
            "mathjax_config": config.mathjax_config,
            "search_form": config.search_form,
            "content_footer": config.content_footer,
            "blog_title": config.blog_title,
            "nav": config.nav_includes,
            "pandoc_options": config.pandoc_output_options,
            "css": config.css,
            "js": config.js,
            "logo_url": Url(config.logo_url) if config.logo_url else None,
            "panflute_filters": config.panflute_output_filters,
            "html_filters": config.html_filters,
        }
        pageses.append(
            page_class.from_file_system(
                path,
                out_path,
                ext,
                template,
                pretty_urls=pretty_urls,
                date_format=config.date_format,
                default_lang=config.default_lang,
                timezone=timezone,
                options=options,
            )
        )
    return pageses


def get_pages(
    PAGES: Tuple[
        Tuple[
            str,  # in-dir
            str,  # out-dir
            str,  # ext
            Optional[Path],  # template
        ],
        ...,
    ],
    config: Config,
    timezone: str = r"America/Los_Angeles",
) -> List[Pages]:
    return _get_pages(Pages, PAGES, config, timezone=timezone)


def get_posts(
    PAGES: Tuple[
        Tuple[
            str,  # in-dir
            str,  # out-dir
            str,  # ext
            Optional[Path],  # template
        ],
        ...,
    ],
    config: Config,
    timezone: str = r"America/Los_Angeles",
) -> List[Posts]:
    return _get_pages(Posts, PAGES, config, timezone=timezone)


def main(config: Config):
    """Parasite static site generator."""
    time_elapse = TimeElapse(logger)

    if config.compress_js:
        minifies_js = [
            app_minify(inputs=[File(path) for path in paths], outputs=[File(out_path)])
            for out_path, paths in config.compress_js.items()
        ]
    if config.compress_css:
        minifies = [
            app_minify(inputs=[File(path) for path in paths], outputs=[File(out_path)])
            for out_path, paths in config.compress_css.items()
        ]
    if config.files_folders:
        rsyncs = [
            app_rsync(in_dir, config.output_dir, out_sub_dir)
            for in_dir, out_sub_dir in config.files_folders.items()
        ]
    time_elapse.report("staging for minifies and rsync.")

    pages = Pages(
        sum(
            (
                pages_.pages
                for pages_ in get_pages(config.pages, config, timezone=config.timezone)
            ),
            [],
        )
    )
    posts = Posts(
        sum(
            (
                pages_.pages
                for pages_ in get_posts(config.posts, config, timezone=config.timezone)
            ),
            [],
        )
    )
    time_elapse.report("glob pages/posts from file system.")

    pages_ast_futures = [
        app_read_md_to_ast(
            config.pandoc_input_options,
            config.panflute_input_filters,
            inputs=[File(str((page.path)))],
        )
        for page in pages.pages
    ]
    posts_ast_futures = [
        app_read_md_to_ast_with_teaser(
            config.pandoc_input_options,
            config.panflute_input_filters,
            inputs=[File(str((page.path)))],
        )
        for page in posts.pages
    ]
    time_elapse.report("staging to get all ASTs.")
    for page, future in zip(pages.pages, pages_ast_futures):
        page.ast = future.result()
    for page, future in zip(posts.pages, posts_ast_futures):
        page.ast, page.teaser = future.result()
    time_elapse.report("got all ASTs.")

    if not config.include_draft:
        pages = Pages([page for page in pages.pages if not page.is_draft])
        posts = Posts([page for page in posts.pages if not page.is_draft])
        time_elapse.report("filter out drafts.")

    posts.sort()
    time_elapse.report("sorting posts.")
    posts.get_neighbor_urls()
    time_elapse.report("get neighbor urls.")

    all_pages: List[Union[Page, Post]] = list(pages.pages) + list(posts.pages)
    output_futures = [
        app_post_to_html(
            page.ast,
            page.root,
            page.prev,
            page.next,
            page.lang,
            page.ext,
            inputs=[] if page.template is None else [File(str((page.template)))],
            outputs=[File(str((config.output_dir / page.out_path)))],
            **page.options,
        )
        for page in all_pages
    ]
    time_elapse.report("staging pages/posts HTML output.")

    # cat index
    options = posts.pages[0].options
    for case, dict_ in (
        ("categories", posts.categories),
        ("tags", posts.tags),
    ):
        for name, cat_posts in dict_.items():
            index_ast = posts_to_index_ast(
                cat_posts,
                name,
                n_jumbotron=config.n_jumbotron,
                n_grid=config.n_grid,
                index_include_jumbotron=config.index_include_jumbotron,
                lang=config.default_lang,
            )
            output_futures.append(
                app_post_to_html(
                    index_ast,
                    "../..",
                    None,
                    None,
                    config.default_lang,
                    ".md",
                    inputs=[]
                    if config.index_template is None
                    else [File(str((config.index_template)))],
                    outputs=[
                        File(
                            str(
                                config.output_dir
                                / "categories"
                                / (name if case == "tags" else f"cat_{name}")
                                / "index.html"
                            )
                        )
                    ],
                    **options,
                )
            )
    time_elapse.report("staging cat-index.")
    # tags
    _template = posts.pages[0].template
    inputs = [] if _template is None else [File(str((_template)))]
    tag_ast = posts_to_tag_ast(
        posts.categories,
        posts.tags,
        font_size_min=config.tag_cloud_font_size_min,
        font_size_max=config.tag_cloud_font_size_max,
        root="..",
        lang=config.default_lang,
    )
    output_futures.append(
        app_post_to_html(
            tag_ast,
            "..",
            None,
            None,
            config.default_lang,
            ".md",
            inputs=inputs,
            outputs=[File(str((config.output_dir / "categories" / "index.html")))],
            **options,
        )
    )
    time_elapse.report("staging tag page.")
    # archive
    archive_ast = posts_to_archive_ast(
        posts.pages,
        root="..",
        lang=config.default_lang,
    )
    output_futures.append(
        app_post_to_html(
            archive_ast,
            "..",
            None,
            None,
            config.default_lang,
            ".md",
            inputs=inputs,
            outputs=[File(str((config.output_dir / "archive" / "index.html")))],
            **options,
        )
    )
    time_elapse.report("staging archive page.")
    # index
    index_ast = posts_to_index_ast(
        posts.pages,
        config.blog_title[config.default_lang],
        n_jumbotron=config.n_jumbotron,
        n_grid=config.n_grid,
        index_include_jumbotron=config.index_include_jumbotron,
        lang=config.default_lang,
    )
    output_futures.append(
        app_post_to_html(
            index_ast,
            ".",
            None,
            None,
            config.default_lang,
            ".md",
            inputs=[]
            if config.index_template is None
            else [File(str((config.index_template)))],
            outputs=[File(str((config.output_dir / "index.html")))],
            **options,
        )
    )
    time_elapse.report("staging index.")
    if config.write_tipuesearch_json:
        # search: we're not using parsl here, as
        # it needs to be re-generated even if only one page is changed,
        # and the time taken is very small for now.
        # as site gets bigger, may need to cache the Page.text e.g. in app_read_md_to_ast*?
        write_tipuesearch(
            config.output_dir / "assets/js/tipuesearch_content.js",
            all_pages,
            root=config.root_relative_to_search_form,
        )
        time_elapse.report("wrote tipuesearch.")

    if config.write_atom or config.write_rss:
        to_feed(
            posts.pages,
            config.blog_title[config.default_lang],
            config.blog_description[config.default_lang],
            config.blog_author[config.default_lang],
            config.blog_email,
            config.site_url,
            config.logo_url,
            config.default_lang,
            config.copyright,
            config.timezone,
            output_dir=config.output_dir,
            write_atom=config.write_atom,
            write_rss=config.write_rss,
        )
        time_elapse.report("wrote rss and/or atom feed.")
    if config.write_sitemap:
        to_sitemap(
            config.site_url,
            all_pages,
            output_dir=config.output_dir,
        )

    for future in output_futures:
        future.result()
    if config.files_folders:
        for rsync in rsyncs:
            rsync.result()
    if config.compress_css:
        for minify in minifies:
            minify.result()
    if config.compress_js:
        for minify in minifies_js:
            minify.result()
    time_elapse.report("collecting all futures.")
    live(all_pages, config)


def cli(Config=Config):
    config = defopt.run(Config, show_types=True, strict_kwonly=False)
    main(config)


if __name__ == "__main__":
    cli()
