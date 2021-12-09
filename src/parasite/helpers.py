from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List, Sequence, Tuple, Union

    from .data import Page, Post


def _nav(
    data: Tuple[Union[Tuple[str, str], Tuple[Tuple[Tuple[str, str], ...], str]], ...],
    ul_class: str = "navbar-nav nav-fill d-flex w-100",
    li_class: str = "nav-item",
    a_class: str = "nav-link",
    dropdown_li_class: str = "nav-item dropdown",
    dropdown_a_class: str = "nav-link dropdown-toggle",
    dropdown_a_attrs: str = 'data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"',
    inner_ul_class: str = "dropdown-menu",
    inner_li_class: str = "dropdown-item",
    inner_a_class: str = "dropdown-item",
) -> List[str]:
    res = [f'<ul class="{ul_class}">']
    for datum in data:
        type_ = type(datum[0])
        if type_ is str:
            url, title = datum
            res.append(
                f'<li class="{li_class}"><a href="{url}"'
                f' class="{a_class}">{title}</a></li>'
            )
        elif type_ is tuple:
            inner_data, title = datum
            res.append(
                f'<li class="{dropdown_li_class}"><a href="#"'
                f' class="{dropdown_a_class}" {dropdown_a_attrs}>{title}</a>'
            )
            res += _nav(
                inner_data,  # type: ignore[arg-type] # recursive type limitation
                ul_class=inner_ul_class,
                li_class=inner_li_class,
                a_class=inner_a_class,
            )
            res.append("</li>")
        else:
            raise TypeError("Unknown type inside nav data: {type_}.")
    res.append("</ul>")
    return res


def nav(
    data: Tuple[Union[Tuple[str, str], Tuple[Tuple[Tuple[str, str], ...], str]], ...]
) -> str:
    return "".join(_nav(data))


def pretty_urls_present(parent: Path, stem: str) -> Path:
    """An example "pretty_urls" callable for present.html"""
    return parent / stem / "present.html"


def tipuesearch(
    pages: Sequence[Page],
    root: str = "..",
) -> Dict[str, List[Dict[str, None | str]]]:
    return {
        "pages": [
            {
                "title": page.title,
                "text": page.text,
                "tags": ",".join(page.tags),
                "url": str(root / page.url),
                # doesn't work
                # 'image': None if page.previewimage is None else str(root / page.previewimage),
            }
            for page in pages
        ]
    }


def write_tipuesearch(
    path: Path,
    pages: Sequence[Page],
    root: str = "..",
) -> None:
    import ujson as json

    data = tipuesearch(pages, root=root)
    with open(path, "w") as f:
        print("var tipuesearch=", file=f, end="")
        json.dump(data, f)


def minify_html(html: str) -> str:
    import subprocess  # nosec

    res = subprocess.run(  # nosec
        [
            "minify",
            "--type=html",
            "--html-keep-conditional-comments",
            "--html-keep-default-attrvals",
            "--html-keep-document-tags",
            "--html-keep-end-tags",
            "--html-keep-quotes",
            "--html-keep-whitespace",
        ],
        input=html,
        text=True,
        capture_output=True,
    )
    if res.returncode != 0:
        raise RuntimeError(res)
    return res.stdout


def to_feed(
    posts: Sequence[Post],
    title: str,
    description: str,
    author: str,
    email: str,
    site_url: str,
    logo_url: str,
    lang: str,
    copy_right: str,
    time_zone: str,
    output_dir: Path = Path("output"),
    write_atom: bool = True,
    write_rss: bool = True,
) -> None:
    import re

    from feedgen.feed import FeedGenerator

    # https://stackoverflow.com/a/25920392/5769446
    regex = re.compile(
        "[^\u0020-\uD7FF\u0009\u000A\u000D\uE000-\uFFFD\U00010000-\U0010FFFF]+"
    )

    fg = FeedGenerator()
    fg.id(site_url)
    fg.link(href=site_url, rel="alternate")
    fg.link(href=site_url + "rss.xml", rel="self")
    fg.title(title)
    fg.author(name=author, email=email)
    fg.logo(site_url + logo_url)
    fg.description(description)
    fg.language(lang)
    fg.rights(copy_right)
    for post in posts:
        url = str(site_url / post.url)

        fe = fg.add_entry()

        fe.id(url)
        fe.title(post.title)
        fe.link(href=url)
        fe.author(name=post.author)
        fe.published(post.time)
        # xml don't like invalid characters that somehow pandoc can produce
        fe.content(regex.sub("", post.html), type="CDATA")

    if write_atom:
        fg.atom_file(str(output_dir / "atom.xml"))
    if write_rss:
        fg.rss_file(str(output_dir / "rss.xml"))


def to_sitemap(
    site_url: str,
    pages: Sequence[Page],
    output_dir: Path = Path("output"),
    filename: str = "sitemapindex.xml",
) -> None:
    from xml.etree.ElementTree import Element, ElementTree, SubElement  # nosec

    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    tree = ElementTree(urlset)

    for page in pages:
        url = SubElement(urlset, "url")

        loc = SubElement(url, "loc")
        loc.text = str(site_url / page.url)

        lastmod = SubElement(url, "lastmod")
        lastmod.text = page.committed_date_str
    tree.write(output_dir / filename, encoding="utf-8", xml_declaration=True)
