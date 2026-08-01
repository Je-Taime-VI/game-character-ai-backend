from __future__ import annotations

from pathlib import Path


STATIC_DIR = Path(__file__).with_name("static")


def get_permissions_page_v2() -> str:
    return (STATIC_DIR / "permissions_v2.html").read_text(encoding="utf-8")
