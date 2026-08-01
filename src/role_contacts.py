from __future__ import annotations

from pathlib import Path
from typing import Any


RAW_ROLE_ROOT = Path("data/raw/角色")
DEFAULT_AVATAR_FILE = "Placeholder.jpg"
DEFAULT_SIGNATURE = "点击开始飞讯对话。"

ROLE_CONTACT_OVERRIDES: dict[str, dict[str, str]] = {
    "守岸人": {
        "avatar_file": "ShouAnRen.png",
    },
    "陆·赫斯": {
        "signature": "不给糖就捣蛋！:'-)",
        "avatar_file": "LuHesi.png",
    },
    "爱弥斯": {
        "signature": "只要抬头，那颗星总能找到我。",
        "avatar_file": "Aimis.png",
    },
    "秧秧": {
        "avatar_file": "Yangyang.png",
    },
}


def list_role_contacts(role_root: Path = RAW_ROLE_ROOT) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    if not role_root.exists():
        return contacts

    for role_dir in sorted((path for path in role_root.iterdir() if path.is_dir()), key=lambda item: item.name):
        role_name = role_dir.name
        override = ROLE_CONTACT_OVERRIDES.get(role_name, {})
        contacts.append(
            {
                "role_name": role_name,
                "signature": override.get("signature") or DEFAULT_SIGNATURE,
                "avatar_file": override.get("avatar_file") or DEFAULT_AVATAR_FILE,
            }
        )
    return contacts
