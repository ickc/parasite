from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from parasite.helpers import nav, pretty_urls_present
from parasite.panflute_filters import lightgallery, lightgallery_from_dir

if TYPE_CHECKING:
    from typing import Callable, Dict, List, Optional, Tuple, Union

SITE_URL: str = ""
BLOG_EMAIL: str = ""
N_JUMBOTRON: int = 1
N_GRID: int = 2
INDEX_INCLUDE_JUMBOTRON: bool = True
TAG_CLOUD_FONT_SIZE_MIN: int = 70
TAG_CLOUD_FONT_SIZE_MAX: int = 280
LOGO_URL: str = ''
SHOW_PREVIEWIMAGE_IN_POST: bool = True

OUTPUT_DIR: Path = Path('output')
DATE_FORMAT: str = r'%Y-%m-%d'
PRETTY_URLS: Dict[str, Union[bool, Callable[[Path, str], Path]]] = {
    '.md': True,
    '.markdown': pretty_urls_present,
}

MATHJAX_CONFIG: str = """"""

DEFAULT_LANG: str = "en"
# keys are lang
BLOG_AUTHOR: Dict[str, str] = {
    'en': '',
}
BLOG_TITLE: Dict[str, str] = {
    'en': "",
}
BLOG_DESCRIPTION: Dict[str, str] = {
    'en': "",
}


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

ROOT_RELATIVE_TO_SEARCH_FORM: str = '..'
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
    return ''


def include_before(lang: str, ext: str, out_ext: str) -> str:
    return ''


def include_after(lang: str, ext: str, out_ext: str) -> str:
    return ''


THIS_YEAR = time.gmtime().tm_year
COPYRIGHT: str = f'Contents © 2021–{THIS_YEAR} {BLOG_AUTHOR[DEFAULT_LANG]}'
TIMEZONE: str = r"America/Los_Angeles"


def content_footer(lang: str, ext: str, out_ext: str) -> str:
    if ext == '.md' and out_ext == '.html':
        return f'Contents © 2021–{THIS_YEAR}         <a href="mailto:{BLOG_EMAIL}">{BLOG_AUTHOR[lang]}</a>'
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


def js(ext: str, out_ext: str) -> List[str]:
    if ext == '.md' and out_ext == 'html':
        return [
            'https://cdn.jsdelivr.net/npm/jquery@3/dist/jquery.min.js',
            'https://cdn.jsdelivr.net/npm/bootstrap@4/dist/js/bootstrap.bundle.min.js',
            'https://cdn.jsdelivr.net/npm/tocbot@4/dist/tocbot.min.js',
            'https://cdn.jsdelivr.net/npm/lightgallery@2/lightgallery.umd.js',
            'https://cdn.jsdelivr.net/npm/lightgallery@2/plugins/thumbnail/lg-thumbnail.umd.js',
            'https://cdn.jsdelivr.net/npm/justifiedGallery@3/dist/js/jquery.justifiedGallery.min.js',
        ]
    else:
        return []


def script_include_after(ext: str, out_ext: str) -> str:
    if ext == '.md' and out_ext == '.html':
        return """tocbot.init({{
  tocSelector: '.js-toc',
  contentSelector: '.entry-content',
  headingSelector: 'h1, h2, h3, h4, h5, h6',
  collapseDepth: 1,
}});"""
    else:
        return ''


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
    f'{OUTPUT_DIR}/assets/js/tipuesearch.js': [
        '_js/tipuesearch_set.js',
        '_js/tipuesearch.js',
    ]
}


def pandoc_input_options(ext: str) -> List[str]:
    return []


def panflute_input_filters(ext: str) -> List[Callable]:
    return [
        lightgallery_from_dir,
    ]


def pandoc_output_options(ext: str, out_ext: str) -> List[str]:
    res = []
    if out_ext == '.html':
        res.append('--mathjax')
    if ext == '.markdown':
        res.append('--to=slidy')
    return res


def panflute_output_filters(ext: str, out_ext: str) -> List[Callable]:
    if out_ext == '.html':
        return [
            lightgallery,
        ]
    else:
        return []


HTML_FILTERS: List[Callable[[str], str]] = []
