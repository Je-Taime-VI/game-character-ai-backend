from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from src.build_metadata import DEFAULT_OUTPUT_PATH, build_metadata, save_metadata
    from src.build_vector_db_with_metadata import build_vector_db
    from src.xlsx_to_editor_json import RAW_ROOT, convert_workbook, default_output_path
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.build_metadata import DEFAULT_OUTPUT_PATH, build_metadata, save_metadata
    from src.build_vector_db_with_metadata import build_vector_db
    from src.xlsx_to_editor_json import RAW_ROOT, convert_workbook, default_output_path


WORKBOOK_SUFFIXES = {".xlsx", ".xlsm", ".xlsl"}
SKIPPED_WORKBOOK_STEMS = {"模板"}


def iter_workbooks(raw_root: Path) -> list[Path]:
    workbooks: list[Path] = []
    for path in raw_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        if path.stem in SKIPPED_WORKBOOK_STEMS:
            continue
        if path.suffix.lower() in WORKBOOK_SUFFIXES:
            workbooks.append(path)
    return sorted(workbooks)


def convert_workbooks(raw_root: Path) -> list[Path]:
    outputs: list[Path] = []
    for workbook_path in iter_workbooks(raw_root):
        output_path = default_output_path(workbook_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        convert_workbook(workbook_path, output_path, raw_root=raw_root)
        outputs.append(output_path)
        print(f"converted: {workbook_path} -> {output_path}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare source data: xlsx -> editor.json -> metadata -> vector_db")
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--metadata-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--skip-xlsx", action="store_true", help="Skip workbook conversion.")
    parser.add_argument("--skip-metadata", action="store_true", help="Skip metadata rebuild.")
    parser.add_argument("--skip-vector", action="store_true", help="Skip vector database rebuild.")
    parser.add_argument("--model-name", default="BAAI/bge-small-zh-v1.5")
    args = parser.parse_args()

    if not args.skip_xlsx:
        outputs = convert_workbooks(args.raw_root)
        print(f"converted workbooks: {len(outputs)}")

    if not args.skip_metadata:
        documents = build_metadata(root=args.raw_root)
        save_metadata(documents, args.metadata_path)
        print(f"metadata: {args.metadata_path} ({len(documents)} documents)")

    if not args.skip_vector:
        paths = build_vector_db(metadata_path=args.metadata_path, model_name=args.model_name, rebuild_metadata=False)
        for name, path in paths.items():
            print(f"{name}: {path}")


if __name__ == "__main__":
    main()
