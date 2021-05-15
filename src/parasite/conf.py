from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING

from parasite.helpers import nav, pretty_urls_present

if TYPE_CHECKING:
    from typing import Tuple, Dict, Optional, List, Union, Callable

# SITE_URL: str = ""
# BLOG_EMAIL: str = ""
N_JUMBOTRON: int = 1
N_GRID: int = 2
INDEX_INCLUDE_JUMBOTRON: bool = True
TAG_CLOUD_FONT_SIZE_MIN: int = 70
TAG_CLOUD_FONT_SIZE_MAX: int = 280

OUTPUT_DIR: Path = Path('output')
DATE_FORMAT: str = r'%Y-%m-%d'
PRETTY_URLS: Dict[str, Union[bool, Callable[[Path, str], Path]]] = {
    '.md': True,
    '.markdown': pretty_urls_present,
}

MATHJAX_CONFIG: str = """"""

DEFAULT_LANG: str = "en"
# keys are lang
# BLOG_AUTHOR: Dict[str, str] = {
#     'en': '',
# }
BLOG_TITLE: Dict[str, str] = {
    'en': "",
}
# BLOG_DESCRIPTION: Dict[str, str] = {
#     'en': "",
# }


# values are output base path relative to root
# TRANSLATIONS: Dict[str, Path] = {
#     DEFAULT_LANG: Path('.'),
# }

# TODO
# files to be copied
# in-dir, out-dir
FILES_FOLDERS: Dict[str, str] = {
    'files': '',
    'media': 'media',
}

# input files for pandoc
POSTS: Tuple[
    Tuple[
        str,           # in-dir
        str,           # out-dir
        str,           # ext
        Optional[str]  # template
    ],
    ...
] = (
    ("posts", "", ".md", "templates/post.html"),
)
PAGES: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    ("pages", "", ".md", "templates/post.html"),
    ("posts", "", ".markdown", "templates/slidy.html"),
)
INDEX_TEMPLATE: Optional[str] = 'templates/index.html'

# these will be formatted by .format(root=root)
# so escape your {}


def search_form(lang: str, ext: str, out_ext: str) -> str:
    if ext == '.md' and out_ext == '.html':
        return """<form class="navbar-form navbar-left" action="{root}/search/" role="search">
    <div class="form-group">
        <input type="text" class="form-control" id="tipue_search_input" name="q" placeholder="Search" autocomplete="off" />
    </div>
</form>"""
    else:
        return ''


def header_includes(lang: str, ext: str, out_ext: str) -> str:
    if ext == '.md' and out_ext == '.html':
        return """<script src="https://cdn.jsdelivr.net/npm/tocbot@4.12.3/dist/tocbot.min.js" integrity="sha256-IwKHOct5ypi59vLt9VBR9zFe77yGT0Z2iuUPsuN0SGo=" crossorigin="anonymous"></script>"""
    else:
        return ''


def include_before(lang: str, ext: str, out_ext: str) -> str:
    return ''


def include_after(lang: str, ext: str, out_ext: str) -> str:
    if ext == '.md' and out_ext == '.html':
        return """<script>
tocbot.init({{
  tocSelector: '.js-toc',
  contentSelector: '.entry-content',
  headingSelector: 'h1, h2, h3, h4, h5, h6',
  hasInnerContainers: true,
  collapseDepth: 1,
}});
</script>"""
    else:
        return ''


def content_footer(lang: str, ext: str, out_ext: str) -> str:
    if ext == '.md' and out_ext == '.html':
        return f'Contents © 2021–{time.gmtime().tm_year}         <a href="mailto:{BLOG_EMAIL}">{BLOG_AUTHOR[lang]}</a>'
    else:
        return ''


def nav_includes(lang: str, ext: str, out_ext: str) -> str:
    if lang == 'en' and ext == '.md' and out_ext == '.html':
        return nav((
            ("{root}/index.html", "Home"),
            ("{root}/about/", 'About'),
            (
                (
                    ("{root}/categories/", "Categories"),
                    ("{root}/archive/", "Archive"),
                ),
                "Archive",
            ),
            # ("{root}/rss.xml", "RSS feed"),
        ))
    else:
        return ''


def pandoc_options(ext: str, out_ext: str) -> List[str]:
    PANDOC_OPTIONS: Dict[
        str,        # input file extension
        List[str],  # pandoc args
    ] = {
        '.md': [
            '--mathjax',
        ],
        '.markdown': [
            '--mathjax',
            '--to=slidy',
        ],
    }
    return PANDOC_OPTIONS[ext]


def css(ext: str, out_ext: str) -> List[str]:
    CSS: Dict[
        str,        # input file extension
        List[str],  # CSS urls
    ] = {
        '.md': [
            '{root}/assets/css/all-nocdn.css',
            'https://fonts.googleapis.com/css?family=Playfair+Display:700,900',
        ],
        '.markdown': [
        ],
    }
    return CSS[ext]


# this will be compressed
CSS: Dict[
    str,       # output file
    List[str]  # input files
] = {
    f'{OUTPUT_DIR}/assets/css/all-nocdn.css': [
        '_css/bootstrap.css',
        '_css/rst_base.css',
        '_css/nikola_rst.css',
        '_css/code.css',
        '_css/baguetteBox.min.css',
        '_css/theme.css',
        '_css/bootblog.css',
        '_css/custom.css',
        '_css/tipuesearch.css',
    ]
}

JS: Dict[
    str,       # output file
    List[str]  # input files
] = {
    f'{OUTPUT_DIR}/assets/js/all-nocdn.js': [
        '_js/jquery.min.js',
        '_js/popper.min.js',
        '_js/bootstrap.min.js',
        '_js/baguetteBox.min.js',
        '_js/fancydates.min.js',
    ],
    f'{OUTPUT_DIR}/assets/js/tipuesearch.js': [
        '_js/tipuesearch_set.js',
        '_js/tipuesearch.js',
    ]
}

HTML_FILTERS: List[Callable[[str], str]] = []
