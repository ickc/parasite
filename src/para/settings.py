"""parasite.toml: a site's configuration, as data.

The site's file is merged over parasite's defaults (``defaults.toml``, which documents
every key), and the result configures a build: :func:`load` returns a :class:`Config`
whose fields and methods come from it. Code runs only from what is installed: filters
are named as importable ``module:function``, never as paths in the site.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import field, make_dataclass
from importlib import import_module, resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .helpers import nav as nav_html
from .helpers import pretty_urls_present
from .site import Config
from .templates import INDEX_TEMPLATE, POST_TEMPLATE, SLIDE_TEMPLATE

if TYPE_CHECKING:
    from typing import Callable, Optional

    from .panflute_filters import PanfluteFilter

FILE = "parasite.toml"
TEMPLATES = {"post": POST_TEMPLATE, "index": INDEX_TEMPLATE, "slides": SLIDE_TEMPLATE}


class SettingsError(ValueError):
    pass


# tables that list a site's own entries: a site's replaces the default whole
WHOLE = {("files",), ("minify", "css"), ("minify", "js")}


def merge(base: dict[str, Any], over: dict[str, Any], at: tuple[str, ...] = ()) -> dict[str, Any]:
    """``over`` merged into ``base``: tables key by key (but those in :data:`WHOLE`),
    anything else replaced."""
    res = dict(base)
    for key, value in over.items():
        here = (*at, key)
        if isinstance(value, dict) and isinstance(res.get(key), dict) and here not in WHOLE:
            res[key] = merge(res[key], value, here)
        else:
            res[key] = value
    return res


def defaults() -> dict[str, Any]:
    return tomllib.loads(resources.files(__package__).joinpath("defaults.toml").read_text(encoding="utf-8"))


def read(path: Path = Path(FILE)) -> dict[str, Any]:
    with open(path, "rb") as f:
        return merge(defaults(), tomllib.load(f))


def _template_string(text: str) -> str:
    """``text`` for the engine's str.format with root and years: every other brace kept."""
    return (
        text.replace("{", "{{")
        .replace("}", "}}")
        .replace("{{root}}", "{root}")
        .replace("{{years}}", "{years}")
    )


def _by_lang(value: Any, lang: str, default_lang: str) -> Any:
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


def _import(spec: str) -> Any:
    module, _, attr = spec.partition(":")
    if not attr:
        raise SettingsError(f"{spec!r}: a filter is 'module:function'")
    obj = import_module(module)
    for name in attr.split("."):
        obj = getattr(obj, name)
    return obj


def _mathjax(table: dict[str, Any]) -> str:
    if not table:
        return ""
    table = dict(table)
    macros_file = table.pop("macros-file", None)
    if macros_file is not None:
        with open(macros_file, encoding="utf-8") as f:
            table.setdefault("tex", {})
            table["tex"] = {**table["tex"], "macros": json.load(f)}
    return f"<script>\nwindow.MathJax = {json.dumps(table, indent=4, ensure_ascii=False)};\n</script>"


def load(path: Path = Path(FILE)) -> type[Config]:
    """The Config class of the site configured by ``path``: its fields' defaults come from
    the file, so the command line can still override them."""
    s = read(path)
    site, listing, profiles = s["site"], s["listing"], s["profiles"]
    lang = site["lang"]

    def per_lang(value: Any) -> dict[str, str]:
        return value if isinstance(value, dict) else {lang: value}

    authors, titles, descriptions = per_lang(site["author"]), per_lang(site["title"]), per_lang(site["description"])

    # which profile renders a source of each extension (one per extension, for now)
    ext_profile: dict[str, str] = {}
    for collection in s["sources"]:
        for ext in collection["ext"]:
            profile = collection["format"][0]
            if ext_profile.setdefault(ext, profile) != profile:
                raise SettingsError(f"{ext} sources are built in both {ext_profile[ext]} and {profile}")
            if profile not in profiles:
                raise SettingsError(f"{collection['dir']}: no profile {profile!r} in [profiles]")

    def profile(ext: str, out_ext: str) -> Optional[dict[str, Any]]:
        if out_ext != ".html" or ext not in ext_profile:
            return None
        return profiles[ext_profile[ext]]

    def part(key: str) -> Callable[..., str]:
        def get(lang_: str, ext: str, out_ext: str) -> str:
            p = profile(ext, out_ext)
            return "" if p is None else _template_string(_by_lang(p[key], lang_, lang) or "")

        return staticmethod(get)

    def template(name: str) -> Path:
        return TEMPLATES[name] if name in TEMPLATES else Path(name)

    def url_rule(rule: str) -> Any:
        if rule == "{stem}/":
            return True
        if rule == "{stem}.html":
            return False
        if rule == "{stem}/present.html":
            return pretty_urls_present
        return lambda parent, stem: parent / rule.format(stem=stem)

    def collections(listed: bool) -> tuple:
        return tuple(
            (c["dir"], c.get("out", ""), ext, template(profiles[c["format"][0]]["template"]), c.get("exclude", []))
            for c in s["sources"]
            if c.get("listed", False) is listed
            for ext in c["ext"]
        )

    filters = s["filters"]
    for name, spec in filters.items():
        if "python" not in spec:
            raise SettingsError(f"[filters.{name}]: only python filters for now")

    def read_filters(ext: str) -> list[PanfluteFilter]:
        return [
            _import(spec["python"])
            for spec in filters.values()
            if spec.get("at", "read") == "read"
            and spec.get("default", False)
            and ("inputs" not in spec or ext.lstrip(".") in spec["inputs"])
        ]

    def render_filters(ext: str, out_ext: str) -> list[PanfluteFilter]:
        p = profile(ext, out_ext)
        if p is None:
            return []
        missing = [name for name in p["filters"] if name not in filters]
        if missing:
            raise SettingsError(f"profile filters {missing} are not in [filters]")
        return [_import(filters[name]["python"]) for name in p["filters"]]

    def read_options(ext: str) -> list[str]:
        return list(s["read"]["options"]) + list(s["read"].get(ext.lstrip("."), {}).get("options", []))

    def render_options(ext: str, out_ext: str) -> list[str]:
        p = profile(ext, out_ext)
        if p is None:
            return []
        return list(p["options"]) + ([] if p["to"] == "html" else [f"--to={p['to']}"])

    def footer(self: Config) -> Callable[[str, str, str], str]:
        def get(lang_: str, ext: str, out_ext: str) -> str:
            p = profile(ext, out_ext)
            if p is None:
                return ""
            text = _by_lang(p["footer"], lang_, lang) or ""
            text = text.replace("{email}", site["email"]).replace("{author}", authors.get(lang_, ""))
            return _template_string(text)

        return get

    def nav(lang_: str, ext: str, out_ext: str) -> str:
        p = profile(ext, out_ext)
        items = None if p is None else _by_lang(p["nav"], lang_, lang)
        return _template_string(nav_html(_nav_data(items))) if items else ""

    def urls(key: str) -> Callable[[str, str], list[str]]:
        def get(ext: str, out_ext: str) -> list[str]:
            p = profile(ext, out_ext)
            return [] if p is None else list(p[key])

        return staticmethod(get)

    def script_include_after(ext: str, out_ext: str) -> str:
        p = profile(ext, out_ext)
        return "" if p is None else _template_string(p["script-include-after"])

    output_dir = Path(site["output"])
    show_images = {p["show-image"] for name, p in profiles.items() if name in ext_profile.values()}
    if len(show_images) > 1:
        raise SettingsError("show-image differs between profiles: not supported yet")
    font_min, font_max = listing["tag-cloud"]
    fields = [
        ("site_url", str, site["url"]),
        ("blog_email", str, site["email"]),
        ("n_jumbotron", int, listing["jumbotron"]),
        ("n_grid", int, listing["grid"]),
        ("index_include_jumbotron", bool, listing["include-jumbotron"]),
        ("tag_cloud_font_size_min", int, font_min),
        ("tag_cloud_font_size_max", int, font_max),
        ("logo_url", str, site["logo"]),
        ("show_image_in_post", bool, show_images.pop() if show_images else True),
        ("output_dir", Path, output_dir),
        ("date_format", str, site["date-format"]),
        ("mathjax_config", str, _mathjax(s["mathjax"])),
        ("default_lang", str, lang),
        ("root_relative_to_search_form", str, s["search"]["root"]),
        ("timezone", str, site["timezone"]),
        ("convert_pdf_media", bool, s["media"]["convert-pdf"]),
        ("write_tipuesearch_json", bool, s["search"]["enabled"]),
        ("write_rss", bool, s["feeds"]["rss"]),
        ("write_atom", bool, s["feeds"]["atom"]),
        ("write_sitemap", bool, s["sitemap"]["enabled"]),
        ("include_draft", bool, site["drafts"]),
        ("index_length", int, listing["index-length"]),
        ("feed_length", int, s["feeds"]["length"]),
        ("write_graph", bool, s["graph"]["enabled"]),
        ("graph_uncoloured", list[str], field(default_factory=lambda: list(s["graph"]["uncoloured"]))),
        ("graph_colours", int, s["graph"]["colours"]),
    ]
    namespace = {
        "copyright": property(
            lambda self: _template_string(site["copyright"].replace("{author}", authors.get(lang, "")))
        ),
        "blog_author": property(lambda self: authors),
        "blog_title": property(lambda self: titles),
        "blog_description": property(lambda self: descriptions),
        "files_folders": property(lambda self: dict(s["files"])),
        "pretty_urls": property(lambda self: {ext: url_rule(profiles[p]["url"]) for ext, p in ext_profile.items()}),
        "posts": property(lambda self: collections(True)),
        "pages": property(lambda self: collections(False)),
        "compress_css": property(lambda self: {f"{output_dir}/{k}": v for k, v in s["minify"].get("css", {}).items()}),
        "compress_js": property(lambda self: {f"{output_dir}/{k}": v for k, v in s["minify"].get("js", {}).items()}),
        "content_footer": property(footer),
        "search_form": part("search-form"),
        "header_includes": part("header-includes"),
        "include_before": part("include-before"),
        "include_after": part("include-after"),
        "nav_includes": staticmethod(nav),
        "css": urls("css"),
        "js": urls("js"),
        "script_include_after": staticmethod(script_include_after),
        "pandoc_input_options": staticmethod(read_options),
        "panflute_input_filters": staticmethod(read_filters),
        "pandoc_output_options": staticmethod(render_options),
        "panflute_output_filters": staticmethod(render_filters),
        "settings": property(lambda self: s),
    }
    return make_dataclass(
        "SiteConfig",
        [(name, type_, value if hasattr(value, "default_factory") else field(default=value)) for name, type_, value in fields],
        bases=(Config,),
        namespace=namespace,
    )

