"""A site's configuration: what a build reads from parasite.toml (see :mod:`para.settings`).

:class:`Config`'s fields are the settings a command line may override; everything else
(collections, output profiles, filters, the page's parts) is read from
:attr:`Config.settings`, the site's parasite.toml merged over parasite's defaults.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from functools import cached_property
from importlib import import_module, resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from custom_inherit import DocInheritMeta

from .helpers import nav as nav_html
from .templates import INDEX_TEMPLATE, POST_TEMPLATE, SLIDE_TEMPLATE

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from .data import Page
    from .panflute_filters import PanfluteFilter

TEMPLATES = {"post": POST_TEMPLATE, "index": INDEX_TEMPLATE, "slides": SLIDE_TEMPLATE}


class SettingsError(ValueError):
    pass


def defaults() -> dict[str, Any]:
    """parasite's defaults (defaults.toml)."""
    return tomllib.loads(resources.files(__package__).joinpath("defaults.toml").read_text(encoding="utf-8"))


def import_filter(spec: str) -> Any:
    """``module:function`` imported."""
    module, _, attr = spec.partition(":")
    if not attr:
        raise SettingsError(f"{spec!r}: a filter is 'module:function'")
    obj = import_module(module)
    for name in attr.split("."):
        obj = getattr(obj, name)
    return obj


def by_lang(value: Any, lang: str, default_lang: str) -> Any:
    """A value, or a table of values by language."""
    if isinstance(value, dict):
        return value.get(lang, value.get(default_lang))
    return value


def _nav_data(items: list[dict[str, Any]]) -> tuple:
    res = []
    for item in items:
        if "menu" in item:
            res.append((_nav_data(item["menu"]), item["text"]))
        else:
            res.append((item["href"], item["text"]))
    return tuple(res)


@dataclass(frozen=True)
class Collection:
    """A folder of sources (``[[sources]]``)."""

    dir: Path
    out: Path
    ext: tuple[str, ...]
    listed: bool
    format: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class Profile:
    """An output profile (``[profiles.NAME]``). Its strings keep ``{root}`` and
    ``{years}``, replaced per page."""

    name: str
    to: str
    template: Path
    url: str
    options: tuple[str, ...]
    filters: tuple[Any, ...]
    show_image: bool
    css: tuple[str, ...]
    js: tuple[str, ...]
    header_includes: Any
    include_before: Any
    include_after: Any
    script_include_after: Any
    nav: Any
    footer: Any
    search_form: Any

    @property
    def pretty(self) -> bool:
        """Its outputs are folders: ``{stem}/`` is ``{stem}/index.html``."""
        return self.url == "{stem}/"

    def out_path(self, parent: Path, stem: str) -> Path:
        if self.pretty:
            # 404 is special: a server serves 404.html, not 404/index.html
            if stem == "404" and parent == Path(""):
                return Path("404.html")
            return parent / stem / "index.html"
        return parent / self.url.format(stem=stem)

    def matches(self, name: str) -> bool:
        """Whether a ``when-format`` names this profile: by its name or its writer."""
        return name in (self.name, self.to)


@dataclass
class Config(metaclass=DocInheritMeta(style="google_with_merge")):  # type: ignore[misc] # mypy limitation
    """Configure static site.

    Args:
        site_url: the site's URL.
        blog_email: the author's email.
        n_jumbotron: posts shown large on the front page.
        n_grid: posts in a grid on the front page after those.
        index_include_jumbotron: list those in the front page's list too.
        tag_cloud_font_size_min: the smallest tag in the tag cloud, in %.
        tag_cloud_font_size_max: the largest tag in the tag cloud, in %.
        logo_url: the site's logo.
        output_dir: the output directory.
        date_format: how dates are written.
        mathjax_config: the MathJax config, a <script>.
        default_lang: the site's language.
        timezone: the time zone of dates without one.
        convert_pdf_media: convert PDF media embedded in sources (e.g. notebook outputs) to SVG.
        write_search: write the search index and page (Pagefind).
        search_page: the search page's path: a folder ("search/") or a file.
        write_rss: write RSS feed.
        write_atom: write atom feed.
        write_sitemap: write sitemap.
        include_draft: output draft posts as well.
        index_length: how many posts the front page shows; older ones are in the archive.
        feed_length: how many of the newest posts the feeds carry.
        write_graph: write the post graph (graph.json and its viewer, needs sitegraph).
        graph_uncoloured: tags never coloured in the graph (they say what form a post takes).
        graph_colours: how many tags the graph colours at first.
    """

    # the merged parasite.toml (see para.settings); a site's class sets its own
    settings: ClassVar[dict[str, Any]] = defaults()

    site_url: str = ""
    blog_email: str = ""
    n_jumbotron: int = 1
    n_grid: int = 2
    index_include_jumbotron: bool = True
    tag_cloud_font_size_min: int = 70
    tag_cloud_font_size_max: int = 280
    logo_url: str = ""
    output_dir: Path = Path("output")
    date_format: str = r"%Y-%m-%d"
    mathjax_config: str = ""
    default_lang: str = "en"
    timezone: str = r"America/Los_Angeles"

    convert_pdf_media: bool = True

    write_search: bool = True
    search_page: str = "search/"
    write_rss: bool = True
    write_atom: bool = True
    write_sitemap: bool = True
    include_draft: bool = False
    index_length: int = 10
    feed_length: int = 10

    write_graph: bool = False
    graph_uncoloured: list[str] = field(default_factory=list)
    graph_colours: int = 7

    # site ####################################################################

    def _per_lang(self, value: Any) -> Dict[str, str]:
        return value if isinstance(value, dict) else {self.default_lang: value}

    @property
    def blog_author(self) -> Dict[str, str]:
        return self._per_lang(self.settings["site"]["author"])

    @property
    def blog_title(self) -> Dict[str, str]:
        return self._per_lang(self.settings["site"]["title"])

    @property
    def blog_description(self) -> Dict[str, str]:
        return self._per_lang(self.settings["site"]["description"])

    @property
    def copyright(self) -> str:
        """The site's copyright line; ``{years}`` becomes its first and last year."""
        return self.settings["site"]["copyright"].replace("{author}", self.blog_author.get(self.default_lang, ""))

    @property
    def files_folders(self) -> Dict[str, str]:
        """Folders of site files, copied whole: source → output folder."""
        return dict(self.settings["files"])

    @property
    def media_folders(self) -> Dict[str, str]:
        """Folders of media, copied by reference: source → output folder."""
        return dict(self.settings["media"].get("folders", {}))

    @property
    def compress_css(self) -> Dict[str, List[str]]:  # output file, input files
        return {f"{self.output_dir}/{k}": v for k, v in self.settings["minify"].get("css", {}).items()}

    @property
    def compress_js(self) -> Dict[str, List[str]]:  # output file, input files
        return {f"{self.output_dir}/{k}": v for k, v in self.settings["minify"].get("js", {}).items()}

    @property
    def index_template(self) -> Optional[Path]:
        return INDEX_TEMPLATE

    @property
    def html_filters(self) -> List[Any]:
        return []

    # sources and profiles ####################################################

    @cached_property
    def collections(self) -> list[Collection]:
        res = []
        for c in self.settings["sources"]:
            for name in c["format"]:
                if name not in self.settings["profiles"]:
                    raise SettingsError(f"[[sources]] {c['dir']}: no profile {name!r} in [profiles]")
            res.append(
                Collection(
                    dir=Path(c["dir"]),
                    out=Path(c.get("out", "")),
                    ext=tuple(c["ext"]),
                    listed=c.get("listed", False),
                    format=tuple(c["format"]),
                    exclude=tuple(c.get("exclude", ())),
                )
            )
        return res

    @cached_property
    def filters(self) -> dict[str, dict[str, Any]]:
        res = self.settings["filters"]
        for name, spec in res.items():
            if "python" not in spec:
                raise SettingsError(f"[filters.{name}]: only python filters for now")
        return res

    @cached_property
    def profiles(self) -> dict[str, Profile]:
        res = {}
        for name, p in self.settings["profiles"].items():
            missing = [f for f in p["filters"] if f not in self.filters]
            if missing:
                raise SettingsError(f"[profiles.{name}]: filters {missing} are not in [filters]")
            navs = p["nav"] if isinstance(p["nav"], dict) else {self.default_lang: p["nav"]}
            res[name] = Profile(
                name=name,
                to=p["to"],
                template=TEMPLATES[p["template"]] if p["template"] in TEMPLATES else Path(p["template"]),
                url=p["url"],
                options=tuple(p["options"]) + (() if p["to"] == "html" else (f"--to={p['to']}",)),
                filters=tuple(import_filter(self.filters[f]["python"]) for f in p["filters"]),
                show_image=p["show-image"],
                css=tuple(p["css"]),
                js=tuple(p["js"]),
                header_includes=p["header-includes"],
                include_before=p["include-before"],
                include_after=p["include-after"],
                script_include_after=p["script-include-after"],
                nav={lang: nav_html(_nav_data(items)) if items else "" for lang, items in navs.items()},
                footer=p["footer"],
                search_form=p["search-form"],
            )
        return res

    @property
    def listing_profile(self) -> Profile:
        """The profile of the derived pages (listings, archive, graph)."""
        return self.profiles[self.settings["listing"]["profile"]]

    def part(self, profile: Profile, name: str, lang: str) -> str:
        """A part of a page (``header_includes``, ``nav``, …) in ``lang``; in the footer,
        ``{email}`` and ``{author}`` are the site's."""
        res = by_lang(getattr(profile, name), lang, self.default_lang) or ""
        if name == "footer":
            res = res.replace("{email}", self.blog_email).replace(
                "{author}", by_lang(self.blog_author, lang, self.default_lang) or ""
            )
        return res

    # reading #################################################################

    def pandoc_input_options(self, ext: str) -> List[str]:
        read = self.settings["read"]
        return list(read["options"]) + list(read.get(ext.lstrip("."), {}).get("options", []))

    def panflute_input_filters(self, ext: str) -> list[PanfluteFilter]:
        return [
            import_filter(spec["python"])
            for spec in self.filters.values()
            if spec.get("at", "read") == "read"
            and spec.get("default", False)
            and ("inputs" not in spec or ext.lstrip(".") in spec["inputs"])
        ]

    def media_options(self, page: Page) -> Dict[str, Any]:
        """Options of :func:`para.apps.read_md_to_ast` resolving media for ``page``."""
        return {
            "out_dir": self.output_dir / page.media_dir,
            "output_dir": self.output_dir,
            # a URL into either kind of folder works from the page
            "files_folders": {**self.files_folders, **self.media_folders},
            "convert_pdf_media": self.convert_pdf_media,
        }


def mathjax_config(table: dict[str, Any]) -> str:
    """The MathJax config <script> from ``[mathjax]``; ``macros-file`` (JSON) is merged
    into ``tex.macros``."""
    if not table:
        return ""
    table = dict(table)
    macros_file = table.pop("macros-file", None)
    if macros_file is not None:
        with open(macros_file, encoding="utf-8") as f:
            table["tex"] = {**table.get("tex", {}), "macros": json.load(f)}
    return f"<script>\nwindow.MathJax = {json.dumps(table, indent=4, ensure_ascii=False)};\n</script>"
