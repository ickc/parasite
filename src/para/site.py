from __future__ import annotations

import io
import json
import os
import shutil
import subprocess  # nosec
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

import defopt
import panflute as pf

from .apps import post_to_html, read_md_to_ast
from .data import Pages, Posts, format_years, root_of
from .helpers import report_urls, to_feed, to_sitemap
from .live import Config as LiveConfig
from .media import media_source, referenced_media
from .output import MEDIA, Output
from .record import Record, by_category, by_tag, by_year, site_years
from .store import Store, hash_key, site_key, source_hash
from .to_ast import (
    posts_to_archive_ast,
    posts_to_archive_index_ast,
    posts_to_index_ast,
    posts_to_tag_ast,
)
from .util import TimeElapse, setup_logging

if TYPE_CHECKING:
    from typing import List, TypeVar

    from .config import Profile
    from .data import Page

    PagesOrPosts = TypeVar("PagesOrPosts", Pages, Posts)

setup_logging()
logger = getLogger(__name__)


def rsync(in_dir: str, out_base_dir: Path, out_sub_dir: str) -> None:
    out_dir = Path(out_base_dir) / out_sub_dir
    out_dir.mkdir(exist_ok=True, parents=True)
    subprocess.run(["rsync", "-a", f"{in_dir}/", f"{out_dir}/"], check=True)  # nosec


def minify(inputs: List[str], output: str) -> None:
    """Bundle ``inputs`` into ``output``, minified with the Go minifier if it is on the
    PATH (https://github.com/tdewolff/minify), else concatenated."""
    output_path = Path(output)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    if shutil.which("minify") is None:
        logger.warning("minify is not on the PATH: %s is concatenated, not minified", output)
        output_path.write_text("\n".join(Path(path).read_text(encoding="utf-8") for path in inputs), encoding="utf-8")
        return
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
        full: read and render everything, ignoring the record store.
        store_path: the record store (see para.store).
    """

    jobs: int = 0
    prune: bool = False
    full: bool = False
    store_path: Path = Path(".para/store.sqlite")

    def output_repr(self) -> str:
        """The config's fields that change the output, for the site key."""
        ignore = {"jobs", "prune", "full", "store_path", "check_links"}
        return repr([(f.name, getattr(self, f.name)) for f in fields(self) if f.name not in ignore and not f.name.startswith(("watch", "serve"))])

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

        # the record store (para.store): what is read and rendered under the same key as
        # last time is not done again
        sources = [page.path for page in [*pages.pages, *posts.pages]]
        if self.write_atom or self.write_rss:
            import feedgen.feed  # noqa: F401  (in the code stamp)
        if self.write_graph:
            import sitegraph.extract  # noqa: F401
        if self.write_search:
            import pagefind.index  # noqa: F401
        key = site_key(
            self.output_repr(),
            sources,
            skip=[self.output_dir, self.store_path.parent],
            copied=[Path(in_dir) for in_dir in [*self.files_folders, *self.media_folders]],
        )
        store = Store(self.store_path, load=not self.full)
        time_elapse.report("site key.")

        def read_ast(page: Page, select: Profile | None, claimed: list[str], pandoc_filters: bool = True) -> pf.Doc:
            """The page's AST, as ``select``'s output sees it (for a source with content
            per profile)."""

            def claim(path: Path) -> None:
                output.claim(path, MEDIA)
                claimed.append(Path(os.path.relpath(path, self.output_dir)).as_posix())

            return read_md_to_ast(
                self.pandoc_input_options,
                self.panflute_input_filters,
                inputs=[page.path],
                **self.media_options(page),
                claim=claim,
                select=select,
                pandoc_filters=pandoc_filters,
            )

        def read(page: Page, post: bool) -> Record:
            """Step 2 and 3: the page's AST, then its record. A source with content per
            profile is read as its first output sees it."""
            claimed: list[str] = []
            select = page.profiles[0] if page.per_profile else None
            page.ast = read_ast(page, select, claimed)
            page.check_metadata()
            page.set_profiles()
            if select is not None and page.profiles[0] is not select:
                # its own format puts another profile first
                page.ast = read_ast(page, page.profiles[0], claimed)
                page.set_profiles()
            page.ast_profile = page.profiles[0] if page.per_profile else None
            # the media every output uses: a source with content per profile is read whole
            # for them (its other outputs are read when rendered)
            whole = read_ast(page, None, claimed, pandoc_filters=False) if page.per_profile else page.ast
            media = referenced_media(whole, self.output_dir / page.media_dir, self.output_dir, self.media_folders)
            record = Record.from_page(page, post, media)
            page.claims = claimed
            return record

        def cached(page: Page) -> Record | None:
            """The page's record from the store, if read under the same key and what the
            read wrote is still there."""
            record = store.record(page.path.as_posix(), page.read_key)
            if record is None:
                return None
            claims = store.claims(record.source)
            if not all((self.output_dir / claim).exists() for claim in claims):
                return None
            for claim in claims:
                output.claim(self.output_dir / claim, MEDIA)
            page.claims = claims
            page.profiles = [self.profiles[name] for name in record.outputs]
            return record

        read_futures = []
        for page, post in [*((p, False) for p in pages.pages), *((p, True) for p in posts.pages)]:
            page.read_key = hash_key(key, page.path.as_posix(), page.out_path.as_posix(), source_hash(page.path))
            if (record := cached(page)) is not None:
                page.record = record
            else:
                read_futures.append((page, pool.submit(read, page, post)))
        time_elapse.report("staging to get all ASTs.")
        for page, future in read_futures:
            page.record = future.result()
            store.put_read(page.record.source, page.read_key, page.record, page.claims)
        store.keep_only(source.as_posix() for source in sources)
        logger.info("read %s of %s sources (the rest unchanged)", len(read_futures), len(sources))
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
        # media, by reference: what the pages built use
        media = sorted({dest for record in all_records for dest in record.media})
        media_copies = [
            pool.submit(output.copy, src, self.output_dir / dest, "media folders")
            for dest in media
            if (src := media_source(dest, self.media_folders)) is not None
        ]
        post_records = [page.record for page in posts.pages]
        reports = report_urls(all_records)
        years = site_years(all_records)
        years_str = format_years(years)
        # Step 4: what crosses pages comes from the records alone. Step 5 renders the
        # derived pages, and each page in its own task; rendering changes the page's AST
        # (includes, output filters), and nothing else reads it any more.
        output_futures = []
        listing_profile = self.listing_profile
        # the index template for listings of posts, the profile's for the rest
        inputs = None
        index_inputs = self.index_template
        renders: dict[str, str] = {}

        def derived(ast: pf.Doc, root: str, out_path: Path, owner: str, template: Path | None) -> None:
            """Render a derived page, unless it was rendered from the same AST last time."""
            rel = Path(os.path.relpath(out_path, self.output_dir)).as_posix()
            renders[rel] = render_key = hash_key(key, rel, root, years_str, json.dumps(ast.to_json(), sort_keys=True))
            if store.renders.get(rel) == render_key and out_path.exists():
                output.claim(out_path, owner)
                return
            output_futures.append(
                pool.submit(
                    post_to_html,
                    ast,
                    root,
                    self.default_lang,
                    listing_profile,
                    out_path,
                    self,
                    template=template,
                    output=output,
                    owner=owner,
                    years=years_str,
                )
            )

        # the listings of posts (none without posts)
        if self.write_listings and post_records:
            # categories and tags
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
                    derived(index_ast, root, self.output_dir / case / name / "index.html", f"{case} {name}", index_inputs)
            # the same overview at /categories/ and /tags/, an AST each: rendering mutates it
            for case in ("categories", "tags"):
                tag_ast = posts_to_tag_ast(
                    by_category(post_records),
                    by_tag(post_records),
                    font_size_min=self.tag_cloud_font_size_min,
                    font_size_max=self.tag_cloud_font_size_max,
                    root="..",
                    lang=self.default_lang,
                )
                derived(tag_ast, "..", self.output_dir / case / "index.html", f"{case} overview", inputs)
            # archive: a page per year, and one linking them
            years_posts = by_year(post_records)
            for year, year_posts in years_posts.items():
                archive_ast = posts_to_archive_ast(year_posts, root="../..", lang=self.default_lang, title=str(year))
                derived(archive_ast, "../..", self.output_dir / "archive" / str(year) / "index.html", f"archive {year}", inputs)
            archive_index = posts_to_archive_index_ast(years_posts, lang=self.default_lang)
            derived(archive_index, "..", self.output_dir / "archive" / "index.html", "archive", inputs)
            # the front page
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
            derived(index_ast, ".", self.output_dir / "index.html", "front page", index_inputs)
        if self.write_graph:
            from .graph import graph_page_ast

            derived(graph_page_ast(lang=self.default_lang), "..", self.output_dir / "graph" / "index.html", "graph page", inputs)
        if self.write_search:
            from .search import search_page_ast

            search = Path(self.search_page + "index.html" if self.search_page.endswith("/") else self.search_page)
            search_root = root_of(search)
            derived(search_page_ast(search_root, lang=self.default_lang), search_root, self.output_dir / search, "search page", inputs)
        time_elapse.report("staging derived pages.")

        feed = {post.out_path for post in post_records[: self.feed_length]} if self.write_atom or self.write_rss else set()

        def render(page: Page) -> tuple[str | None, int]:
            """Step 5 for a page: each of its outputs, unless rendered under the same key
            last time. Returns its HTML fragment if a feed carries it (from the AST as
            read), and how many outputs were rendered. The AST is dropped afterwards."""
            record = page.record
            years_ = format_years(record.years or years)
            in_feed = record.out_path in feed
            fragment = store.fragment(record.source) if in_feed else None
            todo = []
            for profile, out_path in page.outputs:
                report = out_path.as_posix() in reports
                render_key = hash_key(page.read_key, profile.name, years_, report)
                if store.rendered(record.source, profile.name, render_key) and (self.output_dir / out_path).exists():
                    output.claim(self.output_dir / out_path, record.source)
                else:
                    todo.append((profile, out_path, report, render_key))
            if not todo and (fragment is not None or not in_feed):
                return fragment, 0
            if not hasattr(page, "_ast"):
                read(page, record.post)
            if in_feed:
                fragment = page.html
            for i, (profile, out_path, report, render_key) in enumerate(todo):
                if page.per_profile and profile is not page.ast_profile:
                    # its content per profile: read as this output sees it
                    ast = read_ast(page, profile, [])
                elif i == len(todo) - 1 or page.per_profile:
                    ast = page.ast
                else:
                    # rendering changes the AST: a copy for all but the last output
                    ast = pf.load(io.StringIO(json.dumps(page.ast.to_json())))
                if report:
                    ast.metadata["report-url"] = "index.html"
                post_to_html(
                    ast,
                    root_of(out_path),
                    page.lang,
                    profile,
                    self.output_dir / out_path,
                    self,
                    output=output,
                    owner=record.source,
                    years=years_,
                )
                store.put_render(record.source, profile.name, render_key)
            store.put_fragment(record.source, fragment)
            del page.ast
            return fragment, len(todo)

        page_futures = [pool.submit(render, page) for page in all_pages]
        time_elapse.report("staging pages/posts HTML output.")

        if self.write_search:
            from .search import write_pagefind

            write_pagefind(all_records, self.output_dir, output)
            time_elapse.report("wrote the search index.")
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

        fragments = {}
        rendered = 0
        for page, future in zip(all_pages, page_futures):
            fragment, done = future.result()
            rendered += done
            if fragment is not None:
                fragments[page.record.out_path] = fragment
        logger.info("rendered %s of %s outputs (the rest unchanged)", rendered, sum(len(page.outputs) for page in all_pages))
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
        copied = sum(future.result() for future in media_copies)
        logger.info("media: %s files used, %s copied (the rest unchanged)", len(media_copies), copied)
        logger.info("rendered %s of %s derived pages (the rest unchanged)", len(output_futures), len(renders))
        time_elapse.report("collecting all futures.")
        store.renders = renders
        store.save()
        output.finish(prune=self.prune)
        if self.check_links:
            from .check import check_links

            check = self.settings.get("check", {})
            broken = check_links(self.output_dir, check.get("exclude", []), check.get("exclude-path", []))
            time_elapse.report("checked the links.")
            # a build that serves or watches goes on: the links are in its log
            if broken and not (self.watch or self.serve):
                raise SystemExit(f"{broken} broken links (see above), or [check] exclude them")
        self.live(all_pages)


def cli(Config: type[Config] | None = None) -> None:
    """Build the site in the working directory, configured by its parasite.toml (or by
    ``Config``, from a site's own script)."""
    if Config is None:
        from .settings import FILE, load

        Config = load() if Path(FILE).exists() else globals()["Config"]
    config = defopt.run(Config, show_types=True, cli_options="has_default")
    config.exec()


if __name__ == "__main__":
    cli()
