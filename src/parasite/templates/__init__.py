from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Optional

with resources.path(__package__, "index.html") as path:
    INDEX_TEMPLATE: Optional[Path] = path
with resources.path(__package__, "post.html") as path:
    POST_TEMPLATE: Optional[Path] = path
with resources.path(__package__, "slidy.html") as path:
    SLIDE_TEMPLATE: Optional[Path] = path
