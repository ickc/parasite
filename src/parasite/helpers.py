from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from typing import List, Tuple, Union


def _nav(
    data: Tuple[
        Union[
            Tuple[str, str],
            Tuple[Tuple[Tuple[str, str], ...], str]
        ],
        ...
    ],
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
        if type_ == str:
            url, title = datum
            res.append(f'<li class="{li_class}"><a href="{url}" class="{a_class}">{title}</a></li>')
        elif type_ == tuple:
            inner_data, title = datum
            res.append(f'<li class="{dropdown_li_class}"><a href="#" class="{dropdown_a_class}" {dropdown_a_attrs}>{title}</a>')
            res += _nav(inner_data, ul_class=inner_ul_class, li_class=inner_li_class, a_class=inner_a_class)
            res.append('</li>')
        else:
            raise TypeError('Unknown type inside nav data: {type_}.')
    res.append('</ul>')
    return res


def nav(
    data: Tuple[
        Union[
            Tuple[str, str],
            Tuple[Tuple[Tuple[str, str], ...], str]
        ],
        ...
    ]
) -> str:
    return ''.join(_nav(data))


def pretty_urls_present(parent: Path, stem: str) -> Path:
    """An example "pretty_urls" callable for present.html
    """
    return parent / stem / 'present.html'
