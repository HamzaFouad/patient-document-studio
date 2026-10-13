import re

import arabic_reshaper
from bidi.algorithm import get_display


ARABIC = re.compile(r"[\u0600-\u06ff]")


def pdf_display_text(value: str) -> str:
    """Shape Arabic for ReportLab, which otherwise draws disconnected RTL glyphs."""
    lines = []
    for line in value.split("\n"):
        lines.append(get_display(arabic_reshaper.reshape(line)) if ARABIC.search(line) else line)
    return "\n".join(lines)
