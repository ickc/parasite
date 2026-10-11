from __future__ import annotations

import os
import subprocess  # nosec
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import defopt

from .apps import post_to_html, read_md_to_ast, read_md_to_ast_with_teaser
from .data import Pages, Posts
from .helpers import set_report_urls, to_feed, to_sitemap, write_tipuesearch
from .live import Config as LiveConfig
from .to_ast import posts_to_archive_ast, posts_to_index_ast, posts_to_tag_ast
from .util import TimeElapse, setup_logging

if TYPE_CHECKING:
    from typing import List, TypeVar

    from .data import Page

    PagesOrPosts = TypeVar("PagesOrPosts", Pages, Posts)

setup_logging()
logger = getLogger(__name__)


def rsync(in_dir: str, out_base_dir: Path, out_sub_dir: str) -> None:
    out_dir = Path(out_base_dir) / out_sub_dir
    out_dir.mkdir(exist_ok=True, parents=True)
    subprocess.run(["rsync", "-a", f"{in_dir}/", f"{out_dir}/"], check=True)  # nosec


def minify(inputs: List[str], output: str) -> None:
    """minify using the Go minifier

    https://github.com/tdewolff/minify/tree/master/cmd/minify
    """
    output_path = Path(output)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    subprocess.run(  # nosec
        [
            "minify",
            "--type",
            output_path.suffix[1:],
            "-b",
            "-o",
            str(output_path),
            *inputs,
        ],
        check=True,
    )


@dataclass
class Config(LiveConfig):
    """Configure static site.

    Args:
        jobs: number of pages processed at once (default: the number of CPUs).
    """

    jobs: int = 0

    def exec(self) -> None:
        """Parasite static site generator."""
        with ThreadPoolExecutor(max_workers=self.jobs or os.cpu_count()) as pool:
            self._exec(pool)

    def _exec(self, pool: ThreadPoolExecutor) -> None:
        time_elapse = TimeElapse(logger)

        if self.compress_js:
            minifies_js = [
                pool.submit(minify, paths, out_path)
                for out_path, paths in self.compress_js.items()
            ]
        if self.compress_css:
            minifies = [
                pool.submit(minify, paths, out_path)
                for out_path, paths in self.compress_css.items()
            ]
        if self.files_folders:
            rsyncs = [
                pool.submit(rsync, in_dir, self.output_dir, out_sub_dir)
                for in_dir, out_sub_dir in self.files_folders.items()
            ]
        time_elapse.report("staging for minifies and rsync.")

        pages = Pages.from_config(self)
        posts = Posts.from_config(self)
        time_elapse.report("glob pages/posts from file system.")

        pages_ast_futures = [
            pool.submit(
                read_md_to_ast,
                self.pandoc_input_options,
                self.panflute_input_filters,
                inputs=[page.path],
                **self.media_options(page),
            )
            for page in pages.pages
        ]
        posts_ast_futures = [
            pool.submit(
                read_md_to_ast_with_teaser,
                self.pandoc_input_options,
                self.panflute_input_filters,
                inputs=[page.path],
                **self.media_options(page),
            )
            for page in posts.pages
        ]
        time_elapse.report("staging to get all ASTs.")
        for page, future in zip(pages.pages, pages_ast_futures):
            page.ast = future.result()
        for page, future in zip(posts.pages, posts_ast_futures):
            page.ast, page.teaser = future.result()
        time_elapse.report("got all ASTs.")

        if not self.include_draft:
            pages = Pages([page for page in pages.pages if not page.is_draft])
            posts = Posts([page for page in posts.pages if not page.is_draft])
            time_elapse.report("filter out drafts.")

        posts.sort()
        time_elapse.report("sorting posts.")
        posts.get_neighbor_urls()
        time_elapse.report("get neighbor urls.")

        all_pages: List[Page] = list(pages.pages) + list(posts.pages)
        set_report_urls(all_pages)
        output_futures = [
            pool.submit(
                post_to_html,
                page.ast,
                page.root,
                page.prev,
                page.next,
                page.lang,
                page.ext,
                inputs=[] if page.template is None else [page.template],
                outputs=[self.output_dir / page.out_path],
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
                    n_jumbotron=self.n_jumbotron,
                    n_grid=self.n_grid,
                    index_include_jumbotron=self.index_include_jumbotron,
                    lang=self.default_lang,
                )
                output_futures.append(
                    pool.submit(
                        post_to_html,
                        index_ast,
                        "../..",
                        None,
                        None,
                        self.default_lang,
                        ".md",
                        inputs=[]
                        if self.index_template is None
                        else [self.index_template],
                        outputs=[
                            self.output_dir
                            / "categories"
                            / (name if case == "tags" else f"cat_{name}")
                            / "index.html"
                        ],
                        **options,
                    )
                )
        time_elapse.report("staging cat-index.")
        # tags
        _template = posts.pages[0].template
        inputs = [] if _template is None else [_template]
        tag_ast = posts_to_tag_ast(
            posts.categories,
            posts.tags,
            font_size_min=self.tag_cloud_font_size_min,
            font_size_max=self.tag_cloud_font_size_max,
            root="..",
            lang=self.default_lang,
        )
        output_futures.append(
            pool.submit(
                post_to_html,
                tag_ast,
                "..",
                None,
                None,
                self.default_lang,
                ".md",
                inputs=inputs,
                outputs=[self.output_dir / "categories" / "index.html"],
                **options,
            )
        )
        time_elapse.report("staging tag page.")
        # archive
        archive_ast = posts_to_archive_ast(
            posts.pages,
            root="..",
            lang=self.default_lang,
        )
        output_futures.append(
            pool.submit(
                post_to_html,
                archive_ast,
                "..",
                None,
                None,
                self.default_lang,
                ".md",
                inputs=inputs,
                outputs=[self.output_dir / "archive" / "index.html"],
                **options,
            )
        )
        time_elapse.report("staging archive page.")
        # index
        index_ast = posts_to_index_ast(
            posts.pages,
            self.blog_title[self.default_lang],
            n_jumbotron=self.n_jumbotron,
            n_grid=self.n_grid,
            index_include_jumbotron=self.index_include_jumbotron,
            lang=self.default_lang,
        )
        output_futures.append(
            pool.submit(
                post_to_html,
                index_ast,
                ".",
                None,
                None,
                self.default_lang,
                ".md",
                inputs=[] if self.index_template is None else [self.index_template],
                outputs=[self.output_dir / "index.html"],
                **options,
            )
        )
        time_elapse.report("staging index.")
        if self.write_tipuesearch_json:
            # search: not in the pool, as
            # it needs to be re-generated even if only one page is changed,
            # and the time taken is very small for now.
            # as site gets bigger, may need to cache the Page.text e.g. in read_md_to_ast*?
            write_tipuesearch(
                self.output_dir / "assets/js/tipuesearch_content.js",
                all_pages,
                root=self.root_relative_to_search_form,
            )
            time_elapse.report("wrote tipuesearch.")

        if self.write_atom or self.write_rss:
            to_feed(
                posts.pages,
                self.blog_title[self.default_lang],
                self.blog_description[self.default_lang],
                self.blog_author[self.default_lang],
                self.blog_email,
                self.site_url,
                self.logo_url,
                self.default_lang,
                self.copyright,
                self.timezone,
                output_dir=self.output_dir,
                write_atom=self.write_atom,
                write_rss=self.write_rss,
            )
            time_elapse.report("wrote rss and/or atom feed.")
        if self.write_sitemap:
            to_sitemap(
                self.site_url,
                all_pages,
                output_dir=self.output_dir,
            )

        for future in output_futures:
            future.result()
        if self.files_folders:
            for future in rsyncs:
                future.result()
        if self.compress_css:
            for future in minifies:
                future.result()
        if self.compress_js:
            for future in minifies_js:
                future.result()
        time_elapse.report("collecting all futures.")
        self.live(all_pages)


def cli(Config: type[Config] = Config) -> None:
    config = defopt.run(Config, show_types=True, cli_options="has_default")
    config.exec()


if __name__ == "__main__":
    cli()
