"""A site's configuration: what a build reads from parasite.toml (see :mod:`para.settings`).

:class:`Config`'s fields are the settings a command line may override; everything else
(collections, output profiles, filters, the page's parts) is read from
:attr:`Config.settings`, the site's parasite.toml merged over parasite's defaults.
"""

from __future__ import annotations

import json
import subprocess  # nosec
import tomllib
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from custom_inherit import DocInheritMeta

from .filters import Filter, FilterError
from .helpers import nav as nav_html
from .lang import convert_text, lookup, tag
from .lang import name as lang_name
from .templates import INDEX_TEMPLATE, POST_TEMPLATE, SLIDE_TEMPLATE

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from .data import Page

TEMPLATES = {"post": POST_TEMPLATE, "index": INDEX_TEMPLATE, "slides": SLIDE_TEMPLATE}
# the default theme's files (theme/README.md)
THEME = Path(__file__).parent / "theme"


class SettingsError(ValueError):
    pass


def defaults() -> dict[str, Any]:
    """parasite's defaults (defaults.toml)."""
    return tomllib.loads(resources.files(__package__).joinpath("defaults.toml").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def pandoc_version() -> tuple[int, ...]:
    out = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=True).stdout  # nosec
    return tuple(int(part) for part in out.split()[1].split(".") if part.isdigit())


# pandoc 3.11 replaced these with --math-method=NAME[:URL], and warns about each
MATH_FLAGS = ("--mathjax", "--mathml", "--katex", "--webtex", "--gladtex")


def math_method(options: tuple[str, ...]) -> tuple[str, ...]:
    """``options`` with the math flags pandoc ≥ 3.11 deprecates in its new form."""
    if pandoc_version() < (3, 11):
        return options
    res = []
    for option in options:
        name, eq, url = option.partition("=")
        if name in MATH_FLAGS:
            res.append(f"--math-method={name[2:]}" + (f":{url}" if eq else ""))
        else:
            res.append(option)
    return tuple(res)


def writer_options(p: dict[str, Any]) -> tuple[str, ...]:
    """pandoc's options for a profile's writer: a PDF's by its engine (the file's
    extension says PDF), any other by name (HTML is pandoc's default here)."""
    if p["to"] == "pdf":
        return (f"--pdf-engine={p.get('engine', 'typst')}",)
    return () if p["to"] == "html" else (f"--to={p['to']}",)


def by_lang(value: Any, lang: str, default_lang: str) -> Any:
    """A value, or a table of values by language (see :func:`para.lang.lookup`)."""
    if isinstance(value, dict):
        return lookup(value, lang, default_lang)
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
    # None: pandoc's own (a PDF's)
    template: Optional[Path]
    # what links from its other outputs call it (``format-links``)
    label: str
    url: str
    options: tuple[str, ...]
    # the render filters it names (para.filters)
    filters: tuple[str, ...]
    # a PDF's engine (pandoc's --pdf-engine)
    engine: str
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
            # an index source is its folder's page
            if stem == "index":
                return parent / "index.html"
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
        check_links: check the output's links (lychee), failing the build on broken ones.
        write_rss: write RSS feed.
        write_atom: write atom feed.
        write_sitemap: write sitemap.
        include_draft: output draft posts as well.
        index_length: how many posts the front page shows; older ones are in the archive.
        feed_length: how many of the newest posts the feeds carry.
        write_listings: write the listings: the front page, categories, tags, the archive.
        write_graph: write the post graph (graph.json and its viewer, needs paragraphic).
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
    check_links: bool = True
    write_rss: bool = True
    write_atom: bool = True
    write_sitemap: bool = True
    include_draft: bool = False
    index_length: int = 10
    feed_length: int = 10

    write_listings: bool = True
    write_graph: bool = False
    graph_uncoloured: list[str] = field(default_factory=list)
    graph_colours: int = 7

    # site ####################################################################

    def _per_lang(self, value: Any) -> Dict[str, str]:
        """A value by language, its keys BCP 47 tags (see :mod:`para.lang`)."""
        return {tag(k): v for k, v in value.items()} if isinstance(value, dict) else {self.default_lang: value}

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
        return self.settings["site"]["copyright"].replace("{author}", lookup(self.blog_author, self.default_lang) or "")

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
        """Style sheets to bundle: a site's own file, else the default theme's."""
        return {
            f"{self.output_dir}/{k}": [path if Path(path).exists() else str(THEME / path) for path in v]
            for k, v in self.settings["minify"].get("css", {}).items()
        }

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
    def filters(self) -> dict[str, Filter]:
        """The site's filters (``[filters.NAME]``, see :mod:`para.filters`), in order."""
        try:
            res = {name: Filter.from_spec(name, spec) for name, spec in self.settings["filters"].items()}
            for f in res.values():
                f.check()
        except (FilterError, ImportError, AttributeError) as e:
            raise SettingsError(str(e)) from e
        return res

    @cached_property
    def translations(self) -> dict[str, dict[str, str]]:
        """The site's other languages (``[translations]``), by BCP 47 tag: each one's
        ``name`` (its own, see :data:`para.lang.NAMES`), and ``convert``, an OpenCC
        conversion making a page's translation from a page in ``from`` (the site's
        language), when it has none written."""
        res = {}
        for key, value in self.settings.get("translations", {}).items():
            lang = tag(key)
            value = dict(value)
            unknown = set(value) - {"name", "convert", "from"}
            if unknown:
                raise SettingsError(f"[translations.{key}]: unknown keys {sorted(unknown)}")
            res[lang] = {
                "name": value.get("name") or lang_name(lang),
                "convert": value.get("convert", ""),
                "from": tag(value.get("from", self.default_lang)),
            }
        return res

    @cached_property
    def profiles(self) -> dict[str, Profile]:
        res = {}
        for name, p in self.settings["profiles"].items():
            missing = [f for f in p["filters"] if f not in self.filters]
            if missing:
                raise SettingsError(f"[profiles.{name}]: filters {missing} are not in [filters]")
            if read := [f for f in p["filters"] if self.filters[f].at != "render"]:
                raise SettingsError(f"[profiles.{name}]: filters {read} are not at = \"render\"")
            navs = p["nav"] if isinstance(p["nav"], dict) else {self.default_lang: p["nav"]}
            res[name] = Profile(
                name=name,
                to=p["to"],
                label=p.get("label") or name.title(),
                template=TEMPLATES.get(p["template"]) or (Path(p["template"]) if p["template"] else None),
                url=p["url"],
                options=math_method(tuple(p["options"]) + writer_options(p)),
                filters=tuple(p["filters"]),
                engine=p.get("engine", "typst") if p["to"] == "pdf" else "",
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
        res = self.localized(getattr(profile, name), lang) or ""
        if name == "footer":
            res = res.replace("{email}", self.blog_email).replace("{author}", self.localized(self.blog_author, lang) or "")
        return res

    def localized(self, value: Any, lang: str) -> Any:
        """A value, or a table of values by language, in ``lang``. A language made by
        conversion (``[translations]``) without its own value has its source's,
        converted."""
        res = by_lang(value, lang, self.default_lang)
        spec = self.translations.get(tag(lang))
        if isinstance(value, dict) and isinstance(res, str) and spec and spec["convert"] and lookup(value, lang) is None:
            res = convert_text(res, spec["convert"])
        return res

    # reading #################################################################

    def pandoc_input_options(self, ext: str) -> List[str]:
        read = self.settings["read"]
        return list(read["options"]) + list(read.get(ext.lstrip("."), {}).get("options", []))

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
