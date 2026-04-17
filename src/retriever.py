from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from src.build_vector_db_with_metadata import DEFAULT_MODEL_NAME, VECTOR_DB_DIR


def _lazy_import_sentence_transformer():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer


def _lazy_import_faiss():
    import faiss

    return faiss


class Retriever:
    def __init__(
        self,
        vector_db_dir: Path | str = VECTOR_DB_DIR,
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> None:
        self.vector_db_dir = Path(vector_db_dir)
        self.model_name = model_name
        self._model = None

        self.documents = self._load_json("metadata.json", default=[])
        self.flat_entries = self._load_json("flat_entries.json", default=[])
        self.line_entries = self._load_json("line_entries.json", default=[])

        self.flat_index = self._load_index("flat.index")
        self.line_index = self._load_index("line.index")

        self.block_by_id = self._build_block_lookup()

    def _load_json(self, name: str, default: Any) -> Any:
        path = self.vector_db_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_index(self, name: str):
        path = self.vector_db_dir / name
        if not path.exists():
            return None
        faiss = _lazy_import_faiss()
        return faiss.read_index(str(path))

    def _build_block_lookup(self) -> dict[str, dict]:
        lookup: dict[str, dict] = {}
        for doc in self.documents:
            for chunk in doc.get("chunks", []):
                lookup[chunk["chunk_id"]] = chunk
        return lookup

    @property
    def model(self):
        if self._model is None:
            SentenceTransformer = _lazy_import_sentence_transformer()
            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except TypeError:
                self._model = SentenceTransformer(self.model_name)
            except Exception:
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_query(self, query: str) -> np.ndarray:
        vector = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        return vector.astype("float32")

    def retrieve(
        self,
        query: str,
        top_k_flat: int = 5,
        top_k_lines: int = 8,
        allowed_chunk_ids: set[str] | None = None,
        role_permission: dict | None = None,
    ) -> list[dict]:
        results: list[dict] = []
        query_vector = self.embed_query(query)
        if role_permission is not None:
            allowed_chunk_ids = self._resolve_allowed_chunk_ids(role_permission)

        if self.flat_index is not None and self.flat_entries:
            results.extend(self._search_flat(query_vector, top_k_flat, allowed_chunk_ids))

        if self.line_index is not None and self.line_entries:
            results.extend(self._search_hierarchical(query_vector, top_k_lines, allowed_chunk_ids))

        deduped = self._dedupe_results(results)
        return sorted(deduped, key=self._result_sort_key)

    def _resolve_allowed_chunk_ids(self, role_permission: dict) -> set[str]:
        allowed: set[str] = set()
        for doc in self.documents:
            for chunk in doc.get("chunks", []):
                if self._chunk_allowed_by_permission(chunk, role_permission):
                    allowed.add(chunk["chunk_id"])
        return allowed

    @staticmethod
    def _chunk_allowed_by_permission(chunk: dict, role_permission: dict) -> bool:
        metadata = chunk.get("metadata", {})
        path = metadata.get("path", "")

        for spec in role_permission.get("allowed_role_paths", []):
            if Retriever._path_matches_spec(path, spec):
                return True

        for spec in role_permission.get("allowed_world_paths", []):
            if Retriever._path_matches_spec(path, spec):
                return True

        for spec in role_permission.get("allowed_story_paths", []):
            if Retriever._path_matches_spec(path, spec):
                return True

        region_layers = metadata.get("region_layers", [])
        if region_layers:
            granted_regions = {
                entry["region_path"] if isinstance(entry, dict) else entry
                for entry in role_permission.get("allowed_region_layers", [])
            }
            if region_layers[-1] in granted_regions:
                return True

        return False

    @staticmethod
    def _path_matches_spec(path: str, spec: str | dict) -> bool:
        normalized_path = path.strip().strip("/")
        if isinstance(spec, dict):
            return Retriever._path_matches_object_spec(normalized_path, spec)

        normalized_spec = spec.strip().strip("/")
        if not normalized_spec:
            return False
        if normalized_path == normalized_spec:
            return True

        if normalized_spec.endswith("/**"):
            base = normalized_spec[:-3].rstrip("/")
            if not base:
                return True
            return normalized_path.startswith(base + "/")

        if normalized_spec.endswith("/*"):
            base = normalized_spec[:-2].rstrip("/")
            if not base:
                return normalized_path.endswith(".txt") and "/" not in normalized_path
            parent = normalized_path.rsplit("/", 1)[0] if "/" in normalized_path else ""
            return parent == base and normalized_path.endswith(".txt")

        if normalized_spec.endswith(".txt"):
            return False
        return normalized_path.startswith(normalized_spec + "/")

    @staticmethod
    def _path_matches_object_spec(path: str, spec: dict) -> bool:
        raw_path = str(spec.get("path", "")).strip().strip("/")
        mode = str(spec.get("mode", "recursive")).strip()
        if not raw_path:
            return False

        if mode == "exact":
            return path == raw_path
        if mode == "direct_children_txt":
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            return parent == raw_path and path.endswith(".txt")
        if mode == "recursive":
            return path == raw_path or path.startswith(raw_path + "/")
        return False

    def _search_flat(
        self,
        query_vector: np.ndarray,
        top_k: int,
        allowed_chunk_ids: set[str] | None,
    ) -> list[dict]:
        distances, indices = self.flat_index.search(query_vector, min(top_k, len(self.flat_entries)))
        results: list[dict] = []
        for score, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            entry = self.flat_entries[idx]
            if allowed_chunk_ids and entry["id"] not in allowed_chunk_ids:
                continue
            results.append(
                {
                    "chunk_id": entry["id"],
                    "text": entry["text"],
                    "metadata": entry["metadata"],
                    "score": float(score),
                    "match_type": "flat",
                }
            )
        return results

    def _search_hierarchical(
        self,
        query_vector: np.ndarray,
        top_k: int,
        allowed_chunk_ids: set[str] | None,
    ) -> list[dict]:
        distances, indices = self.line_index.search(query_vector, min(top_k, len(self.line_entries)))
        grouped: dict[str, dict] = defaultdict(
            lambda: {"score": float("-inf"), "matched_lines": [], "metadata": None, "match_count": 0}
        )

        for score, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            entry = self.line_entries[idx]
            parent_chunk_id = entry["parent_chunk_id"]
            if allowed_chunk_ids and parent_chunk_id not in allowed_chunk_ids:
                continue
            group = grouped[parent_chunk_id]
            group["score"] = max(group["score"], float(score))
            group["matched_lines"].append(entry["text"])
            group["metadata"] = entry["parent_metadata"]
            group["match_count"] += 1

        results: list[dict] = []
        for parent_chunk_id, payload in grouped.items():
            parent = self.block_by_id.get(parent_chunk_id)
            if not parent:
                continue
            results.append(
                {
                    "chunk_id": parent_chunk_id,
                    "text": parent["text"],
                    "metadata": payload["metadata"],
                    "score": payload["score"],
                    "match_type": "hierarchical",
                    "matched_lines": payload["matched_lines"],
                    "match_count": payload["match_count"],
                }
            )
        return results

    def _dedupe_results(self, results: list[dict]) -> list[dict]:
        best_by_chunk: dict[str, dict] = {}
        for result in results:
            current = best_by_chunk.get(result["chunk_id"])
            if current is None or result["score"] > current["score"]:
                best_by_chunk[result["chunk_id"]] = result
        return list(best_by_chunk.values())

    @classmethod
    def _result_sort_key(cls, result: dict) -> tuple:
        metadata = result.get("metadata", {})
        if result.get("match_type") == "hierarchical":
            return (
                0,
                -result.get("score", 0.0),
                -result.get("match_count", len(result.get("matched_lines", []))),
                cls._story_time_sort_key(metadata) or (10**9, 10**9, 10**9, 10**9, 10**9),
                result.get("chunk_id", ""),
            )
        return (1, -result.get("score", 0.0), result.get("chunk_id", ""))

    @staticmethod
    def _story_time_sort_key(meta: dict) -> tuple | None:
        knowledge_type = meta.get("knowledge_type")
        if knowledge_type not in {"main_story", "side_story"}:
            return None

        path = meta.get("path", "")
        path_obj = Path(path)
        filename = path_obj.name
        if filename in {"简介.txt", "全文.txt"}:
            filename = path_obj.parent.name
        match = re.match(r"^(\d+)(?:-(\d+))?", filename)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2) or 0)
        else:
            major = 10**9
            minor = 10**9

        story_type_order = 0 if knowledge_type == "main_story" else 1
        scene_start_line = int(meta.get("scene_start_line", 0))
        chunk_index = int(meta.get("chunk_index", 0))
        return (major, story_type_order, minor, scene_start_line, chunk_index)
