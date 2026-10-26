"""Minimal HTML selector adapter (bs4 + lxml) with a scrapling-like surface.

ATR's parsers call `.css(selector, adaptive=True)`, read `.attrib`, and use
`.get_all_text(strip=True)`. Those are the only three surfaces they need, so a
thin adapter lets us drop `scrapling`/`patchright` (and with them Chromium)
without rewriting ~900 lines of parsing.

`adaptive=` is accepted and ignored: scrapling's adaptive relocation relied on
saved DOM snapshots and a headless browser. If ATR markup changes we fix the
selector — that is honest and cheap, unlike shipping a stealth browser.
"""

from typing import Iterator, List, Optional, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

try:  # lxml is much faster, but the base image only pins it transitively
    import lxml  # noqa: F401

    _PARSER = "lxml"
except ImportError:  # pragma: no cover - stdlib fallback keeps parsing alive
    _PARSER = "html.parser"


class Element:
    """One tag, exposing the scrapling attributes the parsers use."""

    __slots__ = ("_tag",)

    def __init__(self, tag: Tag):
        self._tag = tag

    @property
    def tag(self) -> str:
        return self._tag.name or ""

    @property
    def attrib(self) -> dict:
        return {
            k: (" ".join(v) if isinstance(v, list) else v)
            for k, v in (self._tag.attrs or {}).items()
        }

    def css(self, selector: str, adaptive: bool = False, **_: object) -> List["Element"]:
        return [Element(t) for t in self._tag.select(selector)]

    def get_all_text(self, strip: bool = True) -> str:
        return self._tag.get_text(" ", strip=strip)

    def __bool__(self) -> bool:
        return True

    def __iter__(self) -> Iterator["Element"]:
        for child in self._tag.children:
            if isinstance(child, Tag):
                yield Element(child)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Element {self.tag}>"


class Selector:
    """Root document, matching the scrapling constructor signature we call."""

    def __init__(
        self,
        html: Union[bytes, str],
        auto_save: bool = False,
        adaptive: bool = False,
        **_: object,
    ):
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")
        self._soup = BeautifulSoup(html or "", _PARSER)

    def css(self, selector: str, adaptive: bool = False, **_: object) -> List[Element]:
        return [Element(t) for t in self._soup.select(selector)]

    def get_all_text(self, strip: bool = True) -> str:
        return self._soup.get_text(" ", strip=strip)

    @property
    def attrib(self) -> dict:
        return {}


def text_of(element: Optional[Element], strip: bool = True) -> str:
    """Safe text extraction for callers that may get no element."""
    return element.get_all_text(strip=strip) if element else ""
