from __future__ import annotations

import json
from pathlib import Path


ROLE_RAW_DIR = Path("data/raw/角色")
OUTPUT_PATH = Path("data/processed/role_infos.json")


FIELD_PREFIXES = {
    "出生": "birthplace",
    "所属": "affiliation",
    "身份": "identity",
    "性别": "gender",
    "共鸣能力": "resonance_ability",
    "武器": "weapon",
    "属性": "attribute",
}


def normalize_text(text: str) -> str:
    return text.replace("\ufeff", "").replace("\r\n", "\n").strip()


def parse_basic_info(text: str) -> dict:
    info: dict[str, str] = {}
    for raw_line in normalize_text(text).split("\n"):
        line = raw_line.strip()
        if not line or "：" not in line:
            continue
        key, value = line.split("：", 1)
        key = key.strip()
        value = value.strip()
        normalized_key = FIELD_PREFIXES.get(key)
        if normalized_key:
            info[normalized_key] = value
        else:
            info[key] = value
    return info


def editor_document_text(path: Path) -> str:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = str(block.get("text", "")).strip()
        if text:
            texts.append(text)
    return "\n".join(texts)


def extract_role_info(role_dir: Path) -> dict | None:
    basic_info_path = role_dir / "基本信息.editor.json"
    if not basic_info_path.exists():
        return None

    parsed = parse_basic_info(editor_document_text(basic_info_path))
    parsed["role_name"] = role_dir.name
    parsed["role_dir"] = role_dir.as_posix()
    parsed["basic_info_path"] = basic_info_path.as_posix()
    return parsed


def extract_all_role_infos(role_root: Path = ROLE_RAW_DIR) -> list[dict]:
    role_infos: list[dict] = []
    for role_dir in sorted(path for path in role_root.iterdir() if path.is_dir()):
        role_info = extract_role_info(role_dir)
        if role_info:
            role_infos.append(role_info)
    return role_infos


def save_role_infos(role_infos: list[dict], output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(role_infos, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    role_infos = extract_all_role_infos()
    output_path = save_role_infos(role_infos)
    print(f"role infos saved to {output_path}")


if __name__ == "__main__":
    main()
