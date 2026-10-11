from __future__ import annotations

import os
import subprocess  # nosec
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import defopt

from .apps import post_to_html, read_md_to_ast
from .data import Pages, Posts, format_years
from .helpers import set_report_urls, to_feed, to_sitemap, write_tipuesearch
from .live import Config as LiveConfig
from .output import MEDIA, Output
from .record import Record, by_category, by_tag, by_year, site_years
from .to_ast import (
    posts_to_archive_ast,
    posts_to_archive_index_ast,
    posts_to_index_ast,
    posts_to_tag_ast,
)
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
        prune: remove the files in the output directory that the build did not produce.
    """

    jobs: int = 0
    prune: bool = False

    def exec(self) -> None:
        """Parasite static site generator."""
        with ThreadPoolExecutor(max_workers=self.jobs or os.cpu_count()) as pool:
            self._exec(pool)

    def _exec(self, pool: ThreadPoolExecutor) -> None:
        time_elapse = TimeElapse(logger)
        output = Output(self.output_dir)

        for out_path in list(self.compress_js) + list(self.compress_css):
            output.claim(Path(out_path), "minify")
        for in_dir, out_sub_dir in self.files_folders.items():
            output.claim_tree(Path(in_dir), self.output_dir / out_sub_dir, f"files_folders {in_dir}")
        if self.compress_js:
            minifies_js = [pool.submit(minify, paths, out_path) for out_path, paths in self.compress_js.items()]
        if self.compress_css:
            minifies = [pool.submit(minify, paths, out_path) for out_path, paths in self.compress_css.items()]
        if self.files_folders:
            rsyncs = [
                pool.submit(rsync, in_dir, self.output_dir, out_sub_dir)
                for in_dir, out_sub_dir in self.files_folders.items()
            ]
        time_elapse.report("staging for minifies and rsync.")

        pages = Pages.from_config(self)
        posts = Posts.from_config(self)
        time_elapse.report("glob pages/posts from file system.")

        def read(page: Page, post: bool) -> Record:
            """Step 2 and 3: the page's AST, then its record."""
            page.ast = read_md_to_ast(
                self.pandoc_input_options,
                self.panflute_input_filters,
                inputs=[page.path],
                **self.media_options(page),
                claim=partial(output.claim, owner=MEDIA),
            )
            page.check_metadata()
            return Record.from_page(page, post)

        read_futures = [pool.submit(read, page, False) for page in pages.pages] + [
            pool.submit(read, page, True) for page in posts.pages
        ]
        time_elapse.report("staging to get all ASTs.")
        for page, future in zip(list(pages.pages) + list(posts.pages), read_futures):
            page.record = future.result()
        time_elapse.report("got all ASTs and records.")

        if not self.include_draft:
            pages = Pages([page for page in pages.pages if not page.record.draft])
            posts = Posts([page for page in posts.pages if not page.record.draft])
            time_elapse.report("filter out drafts.")

        # newest first; sorted() is stable, so posts of the same date keep their order
        posts.pages = sorted(posts.pages, key=lambda page: page.record.time, reverse=True)
        time_elapse.report("sorting posts.")

        all_pages: List[Page] = list(pages.pages) + list(posts.pages)
        all_records = [page.record for page in all_pages]
        post_records = [page.record for page in posts.pages]
        set_report_urls(all_pages)
        years = site_years(all_records)
        years_str = format_years(years)
        # Step 4: what crosses pages comes from the records alone. Step 5 renders the
        # derived pages, and each page in its own task; rendering changes the page's AST
        # (includes, output filters), and nothing else reads it any more.
        output_futures = []

        # cat index
        options = posts.pages[0].options
        for case, dict_ in (
            ("categories", by_category(post_records)),
            ("tags", by_tag(post_records)),
        ):
            for name, cat_posts in dict_.items():
                # categories/a/b/index.html is 3 levels down
                root = "/".join([".."] * (1 + len(Path(name).parts)))
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
                        root,
                        self.default_lang,
                        ".md",
                        inputs=[]
                        if self.index_template is None
                        else [self.index_template],
                        outputs=[self.output_dir / case / name / "index.html"],
                        output=output,
                        owner=f"{case} {name}",
                        **options,
                        years=years_str,
                    )
                )
        time_elapse.report("staging cat-index.")
        # tags
        _template = posts.pages[0].template
        inputs = [] if _template is None else [_template]
        # the same overview at /categories/ and /tags/, an AST each: rendering mutates it
        output_futures += [
            pool.submit(
                post_to_html,
                posts_to_tag_ast(
                    by_category(post_records),
                    by_tag(post_records),
                    font_size_min=self.tag_cloud_font_size_min,
                    font_size_max=self.tag_cloud_font_size_max,
                    root="..",
                    lang=self.default_lang,
                ),
                "..",
                self.default_lang,
                ".md",
                inputs=inputs,
                outputs=[self.output_dir / case / "index.html"],
                output=output,
                owner=f"{case} overview",
                **options,
                years=years_str,
            )
            for case in ("categories", "tags")
        ]
        time_elapse.report("staging tag page.")
        # archive: a page per year, and one linking them
        years_posts = by_year(post_records)
        for year, year_posts in years_posts.items():
            output_futures.append(
                pool.submit(
                    post_to_html,
                    posts_to_archive_ast(
                        year_posts,
                        root="../..",
                        lang=self.default_lang,
                        title=str(year),
                    ),
                    "../..",
                    self.default_lang,
                    ".md",
                    inputs=inputs,
                    outputs=[self.output_dir / "archive" / str(year) / "index.html"],
                    output=output,
                    owner=f"archive {year}",
                    **options,
                    years=years_str,
                )
            )
        output_futures.append(
            pool.submit(
                post_to_html,
                posts_to_archive_index_ast(years_posts, lang=self.default_lang),
                "..",
                self.default_lang,
                ".md",
                inputs=inputs,
                outputs=[self.output_dir / "archive" / "index.html"],
                output=output,
                owner="archive",
                **options,
                years=years_str,
            )
        )
        time_elapse.report("staging archive page.")
        # index
        index_ast = posts_to_index_ast(
            post_records,
            self.blog_title[self.default_lang],
            n_jumbotron=self.n_jumbotron,
            n_grid=self.n_grid,
            index_include_jumbotron=self.index_include_jumbotron,
            lang=self.default_lang,
            length=self.index_length,
            older_url="archive/",
        )
        output_futures.append(
            pool.submit(
                post_to_html,
                index_ast,
                ".",
                self.default_lang,
                ".md",
                inputs=[] if self.index_template is None else [self.index_template],
                outputs=[self.output_dir / "index.html"],
                output=output,
                owner="front page",
                **options,
                years=years_str,
            )
        )
        time_elapse.report("staging index.")
        if self.write_graph:
            from .graph import graph_page_ast

            output_futures.append(
                pool.submit(
                    post_to_html,
                    graph_page_ast(lang=self.default_lang),
                    "..",
                    self.default_lang,
                    ".md",
                    inputs=inputs,
                    outputs=[self.output_dir / "graph" / "index.html"],
                    output=output,
                    owner="graph page",
                    **options,
                    years=years_str,
                )
            )
        feed = {post.out_path for post in post_records[: self.feed_length]} if self.write_atom or self.write_rss else set()

        def render(page: Page) -> str | None:
            """Step 5 for a page, returning its HTML fragment if a feed carries it (from the
            AST as read). The AST is dropped afterwards."""
            fragment = page.html if page.record.out_path in feed else None
            post_to_html(
                page.ast,
                page.root,
                page.lang,
                page.ext,
                inputs=[] if page.template is None else [page.template],
                outputs=[self.output_dir / page.out_path],
                output=output,
                owner=page.record.source,
                **page.options,
                years=format_years(page.record.years or years),
            )
            del page.ast
            return fragment

        page_futures = [pool.submit(render, page) for page in all_pages]
        time_elapse.report("staging pages/posts HTML output.")

        if self.write_tipuesearch_json:
            # one file over all pages (to be replaced by a sharded index)
            write_tipuesearch(
                self.output_dir / "assets/js/tipuesearch_content.js",
                all_records,
                root=self.root_relative_to_search_form,
                output=output,
            )
            time_elapse.report("wrote tipuesearch.")
        if self.write_sitemap:
            to_sitemap(
                self.site_url,
                all_records,
                output_dir=self.output_dir,
                output=output,
            )
        if self.write_graph:
            from .graph import records, write_graph

            write_graph(
                records(all_records, {post.out_path for post in post_records}, self.site_url or None),
                self.output_dir,
                site_url=self.site_url or None,
                uncoloured=self.graph_uncoloured,
                colours=self.graph_colours,
                output=output,
            )
            time_elapse.report("wrote the post graph.")

        fragments = {page.record.out_path: fragment for page, future in zip(all_pages, page_futures) if (fragment := future.result()) is not None}
        time_elapse.report("pages/posts rendered.")
        if self.write_atom or self.write_rss:
            to_feed(
                post_records[: self.feed_length],
                fragments,
                self.blog_title[self.default_lang],
                self.blog_description[self.default_lang],
                self.blog_author[self.default_lang],
                self.blog_email,
                self.site_url,
                self.logo_url,
                self.default_lang,
                self.copyright.format(years=years_str),
                self.timezone,
                output_dir=self.output_dir,
                write_atom=self.write_atom,
                write_rss=self.write_rss,
                output=output,
            )
            time_elapse.report("wrote rss and/or atom feed.")

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
        output.finish(prune=self.prune)
        self.live(all_pages)


def cli(Config: type[Config] = Config) -> None:
    config = defopt.run(Config, show_types=True, cli_options="has_default")
    config.exec()


if __name__ == "__main__":
    cli()
