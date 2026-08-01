from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.build_metadata import DEFAULT_OUTPUT_PATH, build_metadata, save_metadata


VECTOR_DB_DIR = Path("data/vector_db")
DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"


def _lazy_import_sentence_transformer():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer


def _lazy_import_faiss():
    import faiss

    return faiss


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def flatten_documents(documents: list[dict]) -> tuple[list[dict], list[dict]]:
    flat_entries: list[dict] = []
    line_entries: list[dict] = []

    for doc in documents:
        for chunk in doc["chunks"]:
            if chunk.get("retrieval_text"):
                flat_entries.append(
                    {
                        "id": chunk["chunk_id"],
                        "text": chunk.get("text") or chunk["retrieval_text"],
                        "retrieval_text": chunk["retrieval_text"],
                        "metadata": chunk["metadata"],
                    }
                )
            if chunk["line_chunks"]:
                for line_chunk in chunk["line_chunks"]:
                    line_entries.append(
                        {
                            "id": line_chunk["line_id"],
                            "text": line_chunk["text"],
                            "retrieval_text": line_chunk.get("retrieval_text") or line_chunk["text"],
                            "metadata": line_chunk["metadata"],
                            "parent_chunk_id": line_chunk["parent_id"],
                            "parent_text": chunk["text"],
                            "parent_metadata": chunk["metadata"],
                        }
                    )
    return flat_entries, line_entries


def encode_texts(model_name: str, texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    SentenceTransformer = _lazy_import_sentence_transformer()
    try:
        model = SentenceTransformer(model_name, local_files_only=True)
    except TypeError:
        model = SentenceTransformer(model_name)
    except Exception:
        model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.astype("float32")


def build_index(vectors: np.ndarray):
    faiss = _lazy_import_faiss()
    if vectors.size == 0:
        return None
    dimension = vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)
    return index


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_vector_db(
    metadata_path: Path = DEFAULT_OUTPUT_PATH,
    output_dir: Path = VECTOR_DB_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
    rebuild_metadata: bool = True,
) -> dict[str, Path]:
    if rebuild_metadata or not metadata_path.exists():
        documents = build_metadata()
        save_metadata(documents, metadata_path)
    else:
        documents = json.loads(metadata_path.read_text(encoding="utf-8"))

    flat_entries, line_entries = flatten_documents(documents)

    flat_vectors = encode_texts(model_name, [entry.get("retrieval_text") or entry["text"] for entry in flat_entries])
    line_vectors = encode_texts(model_name, [entry.get("retrieval_text") or entry["text"] for entry in line_entries])

    faiss = _lazy_import_faiss()
    output_dir.mkdir(parents=True, exist_ok=True)

    flat_index = build_index(flat_vectors)
    line_index = build_index(line_vectors)

    paths: dict[str, Path] = {
        "metadata": output_dir / "metadata.json",
        "flat_entries": output_dir / "flat_entries.json",
        "line_entries": output_dir / "line_entries.json",
    }
    save_json(paths["metadata"], documents)
    save_json(paths["flat_entries"], flat_entries)
    save_json(paths["line_entries"], line_entries)

    if flat_index is not None:
        paths["flat_index"] = output_dir / "flat.index"
        faiss.write_index(flat_index, str(paths["flat_index"]))
    if line_index is not None:
        paths["line_index"] = output_dir / "line.index"
        faiss.write_index(line_index, str(paths["line_index"]))

    return paths


def main() -> None:
    paths = build_vector_db()
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
