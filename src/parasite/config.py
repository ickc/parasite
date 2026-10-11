from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Union

from custom_inherit import DocInheritMeta

from .helpers import nav, pretty_urls_present
from .panflute_filters import lightgallery_filter, lightgallery_from_dir_filter
from .templates import INDEX_TEMPLATE, POST_TEMPLATE, SLIDE_TEMPLATE

if TYPE_CHECKING:
    from typing import Callable, List, Optional, Tuple, Union

    from .data import Page
    from .panflute_filters import PanfluteFilter

MD_OR_IPYNB = {".md", ".ipynb"}


@dataclass
class Config(metaclass=DocInheritMeta(style="google_with_merge")):  # type: ignore[misc] # mypy limitation
    """Configure static site.

    Args:
        convert_pdf_media: convert PDF media embedded in sources (e.g. notebook outputs) to SVG.
        write_tipuesearch_json: write tipuesearch JSON file.
        write_rss: write RSS feed.
        write_atom: write atom feed.
        write_sitemap: write sitemap.
        include_draft: output draft posts as well.
        write_graph: write the post graph (graph.json and its viewer, needs sitegraph).
        graph_uncoloured: tags never coloured in the graph (they say what form a post takes).
        graph_colours: how many tags the graph colours at first.

    Notes:
        All attributes, properties, and methods must be runtime constant
        (i.e. not changing after initiated),
        to ensure caching works properly.

        That means methods can only be static methods.

        If a method has to depends on self,
        implement it as a property that returns a callable using closure.
        See `content_footer` for an example on how to do this.
    """

    site_url: str = ""
    blog_email: str = ""
    n_jumbotron: int = 1
    n_grid: int = 2
    index_include_jumbotron: bool = True
    tag_cloud_font_size_min: int = 70
    tag_cloud_font_size_max: int = 280
    logo_url: str = ""
    show_image_in_post: bool = True
    output_dir: Path = Path("output")
    date_format: str = r"%Y-%m-%d"
    mathjax_config: str = ""
    default_lang: str = "en"
    root_relative_to_search_form: str = ".."
    timezone: str = r"America/Los_Angeles"

    convert_pdf_media: bool = True

    write_tipuesearch_json: bool = True
    write_rss: bool = True
    write_atom: bool = True
    write_sitemap: bool = True
    include_draft: bool = False

    write_graph: bool = False
    graph_uncoloured: list[str] = field(default_factory=list)
    graph_colours: int = 7

    @property
    def copyright(self) -> str:
        """The site's copyright line; ``{years}`` becomes its first and last year."""
        return "Contents © {years} " + self.blog_author[self.default_lang]

    @property
    def pretty_urls(self) -> Dict[str, Union[bool, Callable[[Path, str], Path]]]:
        return {
            ".md": True,
            ".ipynb": True,
            ".markdown": pretty_urls_present,
        }

    @property
    def blog_author(self) -> Dict[str, str]:
        return {
            "en": "",
        }

    @property
    def blog_title(self) -> Dict[str, str]:
        return {
            "en": "",
        }

    @property
    def blog_description(self) -> Dict[str, str]:
        return {
            "en": "",
        }

    @property
    def files_folders(self) -> Dict[str, str]:
        return {
            "files": "",
            "media": "media",
        }

    def media_options(self, page: Page) -> Dict[str, Any]:
        """Options of :func:`parasite.apps.read_md_to_ast` resolving media for ``page``."""
        return {
            "out_dir": self.output_dir / page.out_path.parent,
            "output_dir": self.output_dir,
            "files_folders": self.files_folders,
            "convert_pdf_media": self.convert_pdf_media,
        }

    @property
    def index_template(self) -> Optional[Path]:
        return INDEX_TEMPLATE

    # input files for pandoc
    @property
    def posts(
        self,
    ) -> Tuple[
        Tuple[
            str,  # in-dir
            str,  # out-dir
            str,  # ext
            Optional[Path],  # template
            list[str],  # excludes
        ],
        ...,
    ]:
        return (
            ("posts", "", ".md", POST_TEMPLATE, []),
            ("posts", "", ".ipynb", POST_TEMPLATE, [".ipynb_checkpoints/**"]),
        )

    @property
    def pages(
        self,
    ) -> Tuple[
        Tuple[
            str,  # in-dir
            str,  # out-dir
            str,  # ext
            Optional[Path],  # template
            list[str],  # excludes
        ],
        ...,
    ]:
        return (
            ("pages", "", ".md", POST_TEMPLATE, []),
            ("pages", "", ".ipynb", POST_TEMPLATE, [".ipynb_checkpoints/**"]),
            ("posts", "", ".markdown", SLIDE_TEMPLATE, []),
        )

    # this will be compressed
    @property
    def compress_css(
        self,
    ) -> Dict[str, List[str]]:  # output file, input files
        return {
            f"{self.output_dir}/assets/css/all-nocdn.css": [
                "_css/bootstrap.css",
                "_css/rst_base.css",
                "_css/nikola_rst.css",
                "_css/code.css",
                "_css/theme.css",
                "_css/bootblog.css",
                "_css/custom.css",
                "_css/tipuesearch.css",
            ]
        }

    @property
    def compress_js(self) -> Dict[str, List[str]]:  # output file, input files
        return {
            f"{self.output_dir}/assets/js/tipuesearch.js": [
                "_js/tipuesearch_set.js",
                "_js/tipuesearch.js",
            ]
        }

    @property
    def html_filters(self) -> List[Callable[[str], str]]:
        return []

    @property
    def content_footer(self) -> Callable[[str, str, str], str]:
        """The footer of a page, formatted with ``{root}`` and ``{years}``: the page's
        own years (``date`` to ``date-modified``), or the site's for an undated page."""
        blog_email = self.blog_email
        blog_author = self.blog_author

        def _content_footer(lang: str, ext: str, out_ext: str) -> str:
            if ext in MD_OR_IPYNB and out_ext == ".html":
                return (
                    "Contents © {years}         <a"
                    f' href="mailto:{blog_email}">{blog_author[lang]}</a>'
                )
            else:
                return ""

        return _content_footer

    @staticmethod
    def search_form(lang: str, ext: str, out_ext: str) -> str:
        if ext in MD_OR_IPYNB and out_ext == ".html":
            return """<form class="navbar-form navbar-left" action="{root}/search/" role="search">
    <div class="form-group">
        <input type="text" class="form-control" id="tipue_search_input" name="q" placeholder="Search" autocomplete="off" />
    </div>
</form>"""
        else:
            return ""

    @staticmethod
    def header_includes(lang: str, ext: str, out_ext: str) -> str:
        return ""

    @staticmethod
    def include_before(lang: str, ext: str, out_ext: str) -> str:
        return ""

    @staticmethod
    def include_after(lang: str, ext: str, out_ext: str) -> str:
        return ""

    @staticmethod
    def nav_includes(lang: str, ext: str, out_ext: str) -> str:
        if lang == "en" and ext in MD_OR_IPYNB and out_ext == ".html":
            return nav(
                (
                    ("{root}/index.html", "Home"),
                    ("{root}/about/", "About"),
                    (
                        (
                            ("{root}/categories/", "Categories"),
                            ("{root}/archive/", "Archive"),
                        ),
                        "Archive",
                    ),
                    # ("{root}/rss.xml", "RSS feed"),
                )
            )
        else:
            return ""

    @staticmethod
    def css(ext: str, out_ext: str) -> List[str]:
        if ext in MD_OR_IPYNB and out_ext == ".html":
            return [
                "{root}/assets/css/all-nocdn.css",
                "https://fonts.googleapis.com/css?family=Playfair+Display:700,900",
            ]
        else:
            return []

    @staticmethod
    def js(ext: str, out_ext: str) -> List[str]:
        if ext in MD_OR_IPYNB and out_ext == ".html":
            return [
                "https://cdn.jsdelivr.net/npm/jquery@3/dist/jquery.min.js",
                "https://cdn.jsdelivr.net/npm/bootstrap@4/dist/js/bootstrap.bundle.min.js",
                "https://cdn.jsdelivr.net/npm/tocbot@4/dist/tocbot.min.js",
                "https://cdn.jsdelivr.net/npm/lightgallery@2/lightgallery.umd.js",
                "https://cdn.jsdelivr.net/npm/lightgallery@2/plugins/thumbnail/lg-thumbnail.umd.js",
                "https://cdn.jsdelivr.net/npm/justifiedGallery@3/dist/js/jquery.justifiedGallery.min.js",
            ]
        else:
            return []

    @staticmethod
    def script_include_after(ext: str, out_ext: str) -> str:
        if ext in MD_OR_IPYNB and out_ext == ".html":
            return """tocbot.init({{
  tocSelector: '.js-toc',
  contentSelector: '.entry-content',
  headingSelector: 'h1, h2, h3, h4, h5, h6',
  collapseDepth: 1,
}});"""
        else:
            return ""

    @staticmethod
    def pandoc_input_options(ext: str) -> List[str]:
        return []

    @staticmethod
    def panflute_input_filters(ext: str) -> list[PanfluteFilter]:
        return [
            lightgallery_from_dir_filter,
        ]

    @staticmethod
    def pandoc_output_options(ext: str, out_ext: str) -> List[str]:
        res = []
        if out_ext == ".html":
            res += ["--mathjax", "--wrap=none"]
        if ext == ".markdown":
            res.append("--to=slidy")
        return res

    @staticmethod
    def panflute_output_filters(ext: str, out_ext: str) -> list[PanfluteFilter]:
        if out_ext == ".html":
            return [
                lightgallery_filter,
            ]
        else:
            return []
