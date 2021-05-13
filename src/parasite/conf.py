from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Tuple, Dict, Optional, Union, List

SITE_URL: str
BLOG_EMAIL: str

DATE_FORMAT: str = r'%Y-%m-%d'
PRETTY_URLS = True
INDEX_DISPLAY_POST_COUNT: int = 10

MATHJAX_CONFIG: str = ''
SEARCH_FORM: str = """<form class="navbar-form navbar-left" action="{root}/search/" role="search">
    <div class="form-group">
        <input type="text" class="form-control" id="tipue_search_input" name="q" placeholder="Search" autocomplete="off" />
    </div>
</form>"""
EXTRA_HEAD_DATA: str = """<script src="https://cdn.jsdelivr.net/npm/tocbot@4.12.3/dist/tocbot.min.js" integrity="sha256-IwKHOct5ypi59vLt9VBR9zFe77yGT0Z2iuUPsuN0SGo=" crossorigin="anonymous"></script>"""
BODY_BEGIN: str = """"""
BODY_END: str = """<script>
tocbot.init({
  tocSelector: '.js-toc',
  contentSelector: '.entry-content',
  headingSelector: 'h1, h2, h3, h4, h5, h6',
  hasInnerContainers: true,
  collapseDepth: 1,
});
</script>"""

DEFAULT_LANG: str = "en"
TRANSLATIONS_PATTERN: str = '{path}.{lang}.{ext}'  # TODO
# keys are lang
BLOG_AUTHOR: Dict[str, str]
BLOG_TITLE: Dict[str, str]
BLOG_DESCRIPTION: Dict[str, str]  # TODO
NAVIGATION_LINKS: Dict[
    str,
    Tuple[
        Union[
            Tuple[str, str],              # url, name
            Tuple[Tuple[str, str], str],  # sub-menu (tuple of (url, name)), name
        ],
        ...,
    ]
] = {
    DEFAULT_LANG: (
        ("{root}/index.html", "Home"),
        ("{root}/about/", 'About'),
        (
            (
                ("{root}/categories/", "Categories"),
                ("{root}/archive/", "Archive"),
            ),
            "Archive",
        ),
        ("{root}/rss.xml", "RSS feed"),
    )
}
# values are output base path relative to root
TRANSLATIONS: Dict[str, Path] = {
    DEFAULT_LANG: Path('.'),
}

CONTENT_FOOTER: str = 'Contents © {date}         <a href="mailto:{email}">{author}</a>'
# will be pass to format CONTENT_FOOTER
CONTENT_FOOTER_FORMATS: Dict[
    str,
    Tuple[
        Tuple[str, ...],  # args for format
        Dict[str, str],  # kwargs for format
    ],
] = {
    DEFAULT_LANG: (
        (),
        {
            "email": BLOG_EMAIL,
            "author": BLOG_AUTHOR[DEFAULT_LANG],
            "date": str(time.gmtime().tm_year),
        }
    )
}

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
    ("posts", "", ".md", None),
    ("posts", "", ".markdown", None),
)
PAGES: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    ("pages", "", ".md", None),
)

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

CSS: Dict[
    str,        # input file extension
    List[str],  # CSS urls
] = {
    '.md': [
        '{root}/assets/css/all-nocdn.css',
        'https://fonts.googleapis.com/css?family=Playfair+Display:700,900',
    ],
    '.markdown': [
    ]
}
