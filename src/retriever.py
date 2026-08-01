from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

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
        top_k_story: int = 1,
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
        high_score_results = self._select_high_score_results(deduped, limit=top_k_flat + top_k_lines)
        focused_results = self._focus_story_results(high_score_results, limit=top_k_story)
        ordered_results = sorted(focused_results, key=self._chronological_result_sort_key)
        return self._append_deduped_annotations(ordered_results)

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

        if metadata.get("retrieval_mode") == "premise":
            for spec in role_permission.get("allowed_story_premises", []):
                if Retriever._premise_matches_spec(metadata, spec):
                    return True
        elif metadata.get("retrieval_mode") == "aggregate":
            for spec in role_permission.get("allowed_story_segments", []):
                if Retriever._story_segment_matches_spec(metadata, spec):
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
    def _premise_matches_spec(metadata: dict, spec: dict) -> bool:
        if not isinstance(spec, dict):
            return False
        if metadata.get("premise_type") != spec.get("premise_type"):
            return False
        try:
            if int(metadata.get("block_index")) != int(spec.get("block_index")):
                return False
        except (TypeError, ValueError):
            return False
        return Retriever._path_matches_spec(str(metadata.get("path", "")), {"path": spec.get("path", ""), "mode": "exact"})

    @staticmethod
    def _story_segment_matches_spec(metadata: dict, spec: dict) -> bool:
        if not isinstance(spec, dict):
            return False
        if not Retriever._path_matches_spec(str(metadata.get("path", "")), {"path": spec.get("path", ""), "mode": "exact"}):
            return False
        try:
            chunk_start = int(metadata.get("aggregate_start"))
            chunk_end = int(metadata.get("aggregate_end"))
            allowed_start = int(spec.get("aggregate_start"))
            allowed_end = int(spec.get("aggregate_end"))
        except (TypeError, ValueError):
            return False
        if metadata.get("aggregate_type") == "scene":
            return chunk_start <= allowed_end and allowed_start <= chunk_end
        return allowed_start <= chunk_start and chunk_end <= allowed_end

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
        if Retriever._equivalent_editor_txt_paths(normalized_path, normalized_spec):
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
        if normalized_spec.endswith(".editor.json"):
            return False
        return normalized_path.startswith(normalized_spec + "/")

    @staticmethod
    def _path_matches_object_spec(path: str, spec: dict) -> bool:
        raw_path = str(spec.get("path", "")).strip().strip("/")
        mode = str(spec.get("mode", "recursive")).strip()
        if not raw_path:
            return False

        if mode == "exact":
            return path == raw_path or Retriever._equivalent_editor_txt_paths(path, raw_path)
        if mode == "direct_children_txt":
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            return parent == raw_path and path.endswith(".txt")
        if mode == "recursive":
            return path == raw_path or path.startswith(raw_path + "/")
        return False

    @staticmethod
    def _equivalent_editor_txt_paths(left: str, right: str) -> bool:
        left = left.strip().strip("/")
        right = right.strip().strip("/")
        if left.endswith(".editor.json"):
            return left[: -len(".editor.json")] + ".txt" == right
        if right.endswith(".editor.json"):
            return right[: -len(".editor.json")] + ".txt" == left
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
            parent = self.block_by_id.get(entry["id"], {})
            results.append(
                {
                    "chunk_id": entry["id"],
                    "text": parent.get("text") or entry["text"],
                    "metadata": parent.get("metadata") or entry["metadata"],
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
            lambda: {
                "score": float("-inf"),
                "matched_entries": [],
                "metadata": None,
                "match_count": 0,
                "parent_text": "",
            }
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
            group["matched_entries"].append(entry)
            group["metadata"] = entry["parent_metadata"]
            group["match_count"] += 1
            group["parent_text"] = entry.get("parent_text", "")

        results: list[dict] = []
        for parent_chunk_id, payload in grouped.items():
            parent = self.block_by_id.get(parent_chunk_id, {})
            parent_text = parent.get("text") or payload.get("parent_text", "")
            if not parent_text:
                continue
            results.append(
                {
                    "chunk_id": parent_chunk_id,
                    "text": parent_text,
                    "metadata": payload["metadata"],
                    "score": payload["score"],
                    "match_type": "hierarchical",
                    "matched_lines": self._expand_matched_lines(payload["metadata"], payload["matched_entries"]),
                    "matched_line_metadata": [
                        entry.get("metadata", {})
                        for entry in payload["matched_entries"]
                    ],
                    "match_count": payload["match_count"],
                }
            )
        return results

    @staticmethod
    def _expand_matched_lines(parent_metadata: dict | None, matched_entries: list[dict], radius: int = 2) -> list[str]:
        metadata = parent_metadata or {}
        aggregate_blocks = [
            block
            for block in metadata.get("aggregate_blocks", []) or []
            if isinstance(block, dict)
        ]
        if not aggregate_blocks:
            return Retriever._dedupe_texts(
                str(entry.get("text", "")).strip()
                for entry in matched_entries
                if str(entry.get("text", "")).strip()
            )

        order_to_position: dict[int, int] = {}
        for position, block in enumerate(aggregate_blocks):
            try:
                order_to_position[int(block.get("block_index"))] = position
            except (TypeError, ValueError):
                continue

        selected_positions: set[int] = set()
        for entry in matched_entries:
            entry_metadata = entry.get("metadata", {}) or {}
            try:
                block_index = int(entry_metadata.get("block_index"))
            except (TypeError, ValueError):
                continue
            position = order_to_position.get(block_index)
            if position is None:
                continue
            block_type = str(aggregate_blocks[position].get("block_type", "")).strip()
            if block_type == "branch":
                selected_positions.add(position)
                continue
            selected_positions.update(range(max(0, position - radius), min(len(aggregate_blocks), position + radius + 1)))

        if not selected_positions:
            return Retriever._dedupe_texts(
                str(entry.get("text", "")).strip()
                for entry in matched_entries
                if str(entry.get("text", "")).strip()
            )
        return Retriever._dedupe_texts(
            str(aggregate_blocks[position].get("text", "")).strip()
            for position in sorted(selected_positions)
            if str(aggregate_blocks[position].get("text", "")).strip()
        )

    @staticmethod
    def _dedupe_texts(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            output.append(text)
        return output

    def _dedupe_results(self, results: list[dict]) -> list[dict]:
        best_by_chunk: dict[str, dict] = {}
        for result in results:
            current = best_by_chunk.get(result["chunk_id"])
            if current is None or self._result_better_for_dedupe(result, current):
                best_by_chunk[result["chunk_id"]] = result
        return list(best_by_chunk.values())

    @staticmethod
    def _result_better_for_dedupe(candidate: dict, current: dict) -> bool:
        candidate_score = float(candidate.get("score", 0.0))
        current_score = float(current.get("score", 0.0))
        if candidate_score != current_score:
            return candidate_score > current_score

        # If a line-level hit and a parent-level hit tie, keep the parent result
        # with matched_lines: the line is only a locator, while text remains the full scene/paragraph.
        candidate_has_line_hits = bool(candidate.get("matched_lines"))
        current_has_line_hits = bool(current.get("matched_lines"))
        if candidate_has_line_hits != current_has_line_hits:
            return candidate_has_line_hits

        return len(str(candidate.get("text", ""))) > len(str(current.get("text", "")))

    @staticmethod
    def _append_deduped_annotations(results: list[dict]) -> list[dict]:
        seen_terms: set[str] = set()
        output: list[dict] = []
        for result in results:
            item = dict(result)
            metadata = item.get("metadata", {})
            annotations = []
            for annotation in metadata.get("annotations", []) or []:
                if not isinstance(annotation, dict):
                    continue
                term = str(annotation.get("term", "")).strip()
                definition = str(annotation.get("definition", "")).strip()
                if not term or term in seen_terms:
                    continue
                seen_terms.add(term)
                annotations.append((term, definition))
            if annotations:
                annotation_text = "\n".join(
                    f"{term}: {definition}" if definition else term
                    for term, definition in annotations
                )
                item["text"] = f"{item.get('text', '').rstrip()}\n\n[设定]\n{annotation_text}".strip()
            output.append(item)
        return output

    @classmethod
    def _select_high_score_results(cls, results: list[dict], limit: int) -> list[dict]:
        if limit <= 0:
            return []
        return sorted(results, key=cls._score_sort_key)[:limit]

    @classmethod
    def _focus_story_results(cls, results: list[dict], limit: int = 1) -> list[dict]:
        if limit < 0:
            return results

        aggregate_results = [result for result in results if cls._is_story_aggregate_result(result)]
        if not aggregate_results:
            return cls._limit_story_results(results, limit=limit)

        best_aggregates = sorted(aggregate_results, key=cls._score_sort_key)[: max(1, limit)]
        merged_aggregates = [
            cls._merge_story_aggregate_by_paragraph_center(best, aggregate_results)
            for best in best_aggregates
        ]
        selected_ids = {result.get("chunk_id") for result in aggregate_results}
        selected_story_paths = {
            str(result.get("metadata", {}).get("path", "")).strip()
            for result in merged_aggregates
            if str(result.get("metadata", {}).get("path", "")).strip()
        }
        remainder = [
            result
            for result in results
            if result.get("chunk_id") not in selected_ids
            and not cls._is_redundant_summary_premise(result, selected_story_paths)
        ]
        return merged_aggregates + remainder

    @staticmethod
    def _score_sort_key(result: dict) -> tuple:
        return (
            -float(result.get("score", 0.0)),
            -int(result.get("match_count", len(result.get("matched_lines", [])))),
            result.get("chunk_id", ""),
        )

    @classmethod
    def _limit_story_results(cls, results: list[dict], limit: int = 1) -> list[dict]:
        if limit < 0:
            return results

        premise_results = [result for result in results if cls._is_premise_result(result)]
        story_results = [result for result in results if cls._is_story_result(result) and not cls._is_premise_result(result)]
        non_story_results = [result for result in results if not cls._is_story_result(result)]
        if not story_results:
            return results

        kept_story_results = sorted(story_results, key=cls._score_sort_key)[:limit]
        return kept_story_results + premise_results + non_story_results

    @staticmethod
    def _is_story_result(result: dict) -> bool:
        return result.get("metadata", {}).get("knowledge_type") in {"main_story", "side_story"}

    @staticmethod
    def _is_premise_result(result: dict) -> bool:
        metadata = result.get("metadata", {})
        return metadata.get("retrieval_mode") == "premise" or bool(metadata.get("premise_type"))

    @staticmethod
    def _is_story_aggregate_result(result: dict) -> bool:
        metadata = result.get("metadata", {})
        return (
            metadata.get("knowledge_type") in {"main_story", "side_story"}
            and metadata.get("retrieval_mode") == "aggregate"
        )

    @staticmethod
    def _is_redundant_summary_premise(result: dict, selected_story_paths: set[str]) -> bool:
        metadata = result.get("metadata", {})
        return (
            metadata.get("retrieval_mode") == "premise"
            and metadata.get("premise_type") in {"chapter_summary", "paragraph_summary"}
            and str(metadata.get("path", "")).strip() in selected_story_paths
        )

    @classmethod
    def _merge_story_aggregate_by_paragraph_center(cls, best: dict, candidates: list[dict]) -> dict:
        best_meta = best.get("metadata", {})
        best_range = cls._aggregate_range(best_meta)
        if best_range is None:
            return best
        same_path_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("metadata", {}).get("path") == best_meta.get("path")
            and cls._aggregate_range(candidate.get("metadata", {})) is not None
        ]

        center = cls._select_paragraph_center(best, same_path_candidates)
        center_range = cls._aggregate_range(center.get("metadata", {}))
        if center_range is None:
            return best

        scene_supplements = [
            candidate
            for candidate in same_path_candidates
            if candidate.get("metadata", {}).get("aggregate_type") == "scene"
            and cls._ranges_overlap(center_range, cls._aggregate_range(candidate.get("metadata", {})))
        ]
        merge_parts = [center, *scene_supplements]
        merge_parts = cls._dedupe_results_by_chunk_id(merge_parts)
        if len(merge_parts) == 1:
            return center
        return cls._compose_merged_story_result(center, merge_parts)

    @classmethod
    def _select_paragraph_center(cls, best: dict, candidates: list[dict]) -> dict:
        best_meta = best.get("metadata", {})
        if best_meta.get("aggregate_type") == "paragraph":
            return best
        best_range = cls._aggregate_range(best_meta)
        if best_range is None:
            return best
        paragraph_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("metadata", {}).get("aggregate_type") == "paragraph"
            and cls._ranges_overlap(best_range, cls._aggregate_range(candidate.get("metadata", {})))
        ]
        if not paragraph_candidates:
            return best

        hit_block_indices = cls._matched_block_indices(best)
        if hit_block_indices:
            containing = [
                candidate
                for candidate in paragraph_candidates
                if cls._range_contains_any(cls._aggregate_range(candidate.get("metadata", {})), hit_block_indices)
            ]
            if containing:
                return sorted(containing, key=cls._score_sort_key)[0]

        return sorted(
            paragraph_candidates,
            key=lambda candidate: (
                -cls._range_overlap_size(best_range, cls._aggregate_range(candidate.get("metadata", {}))),
                *cls._score_sort_key(candidate),
            ),
        )[0]

    @staticmethod
    def _matched_block_indices(result: dict) -> set[int]:
        output: set[int] = set()
        metadata = result.get("metadata", {})
        for key in ("block_index", "matched_block_index"):
            try:
                output.add(int(metadata[key]))
            except (KeyError, TypeError, ValueError):
                pass
        for item in result.get("matched_block_indices", []) or metadata.get("matched_block_indices", []) or []:
            try:
                output.add(int(item))
            except (TypeError, ValueError):
                pass
        for line in result.get("matched_line_metadata", []) or []:
            if not isinstance(line, dict):
                continue
            try:
                output.add(int(line["block_index"]))
            except (KeyError, TypeError, ValueError):
                pass
        return output

    @staticmethod
    def _range_contains_any(value_range: tuple[int, int] | None, indices: set[int]) -> bool:
        if value_range is None:
            return False
        start, end = value_range
        return any(start <= index <= end for index in indices)

    @staticmethod
    def _range_overlap_size(left: tuple[int, int], right: tuple[int, int] | None) -> int:
        if right is None:
            return 0
        start = max(left[0], right[0])
        end = min(left[1], right[1])
        return max(0, end - start + 1)

    @staticmethod
    def _dedupe_results_by_chunk_id(results: list[dict]) -> list[dict]:
        output: list[dict] = []
        seen: set[str] = set()
        for result in results:
            chunk_id = str(result.get("chunk_id", ""))
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            output.append(result)
        return output

    @staticmethod
    def _aggregate_range(metadata: dict) -> tuple[int, int] | None:
        try:
            return int(metadata["aggregate_start"]), int(metadata["aggregate_end"])
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _ranges_overlap(left: tuple[int, int], right: tuple[int, int] | None) -> bool:
        if right is None:
            return False
        return left[0] <= right[1] and right[0] <= left[1]

    @classmethod
    def _compose_merged_story_result(cls, best: dict, parts: list[dict]) -> dict:
        part_metas = [part.get("metadata", {}) for part in parts]
        ranges = [cls._aggregate_range(meta) for meta in part_metas]
        valid_ranges = [item for item in ranges if item is not None]
        if not valid_ranges:
            return best
        aggregate_start = min(item[0] for item in valid_ranges)
        aggregate_end = max(item[1] for item in valid_ranges)
        earliest_meta = min(part_metas, key=lambda meta: cls._aggregate_range(meta) or (10**9, 10**9))
        merged_metadata = dict(best.get("metadata", {}))
        merged_metadata["retrieval_mode"] = "aggregate"
        merged_metadata["aggregate_type"] = "merged"
        merged_metadata["aggregate_start"] = aggregate_start
        merged_metadata["aggregate_end"] = aggregate_end
        merged_metadata["scene_start_line"] = aggregate_start
        if earliest_meta.get("chapter_note_context"):
            merged_metadata["chapter_note_context"] = earliest_meta["chapter_note_context"]
            merged_metadata["chapter_note"] = str(earliest_meta["chapter_note_context"].get("text", "")).strip()
        elif "chapter_note" in merged_metadata:
            merged_metadata.pop("chapter_note", None)
            merged_metadata.pop("chapter_note_context", None)

        block_by_index: dict[int, dict] = {}
        for meta in part_metas:
            for block in meta.get("aggregate_blocks", []) or []:
                if not isinstance(block, dict):
                    continue
                try:
                    block_index = int(block.get("block_index"))
                except (TypeError, ValueError):
                    continue
                block_by_index[block_index] = block
        aggregate_blocks = [block_by_index[index] for index in sorted(block_by_index)]
        merged_metadata["aggregate_blocks"] = aggregate_blocks

        annotations: dict[str, dict] = {}
        for meta in part_metas:
            for annotation in meta.get("annotations", []) or []:
                if isinstance(annotation, dict) and annotation.get("term"):
                    annotations.setdefault(str(annotation["term"]), annotation)
        merged_metadata["annotations"] = [annotations[key] for key in sorted(annotations)]

        included_notes: dict[int, dict] = {}
        for meta in part_metas:
            for note in meta.get("included_chapter_notes", []) or []:
                if not isinstance(note, dict):
                    continue
                try:
                    note_index = int(note.get("block_index"))
                except (TypeError, ValueError):
                    continue
                if aggregate_start <= note_index <= aggregate_end:
                    included_notes[note_index] = note
        if included_notes:
            merged_metadata["included_chapter_notes"] = [included_notes[index] for index in sorted(included_notes)]
        else:
            merged_metadata.pop("included_chapter_notes", None)

        text_parts: list[str] = []
        chapter_summary = str(merged_metadata.get("chapter_summary", "")).strip()
        if chapter_summary:
            text_parts.extend([f"[\u672c\u7ae0\u6897\u6982]{chapter_summary}", ""])
        chapter_note = str(merged_metadata.get("chapter_note", "")).strip()
        if chapter_note:
            text_parts.extend(["[\u672c\u7ae0\u6ce8\u91ca]", chapter_note, ""])
        text_parts.extend(str(block.get("text", "")).strip() for block in aggregate_blocks if str(block.get("text", "")).strip())

        merged = dict(best)
        merged["chunk_id"] = f"{best.get('chunk_id', '')}::merged::{aggregate_start}-{aggregate_end}"
        merged["text"] = "\n".join(text_parts).strip()
        merged["metadata"] = merged_metadata
        merged["score"] = max(float(part.get("score", 0.0)) for part in parts)
        merged["match_type"] = "hierarchical"
        merged["matched_lines"] = cls._dedupe_texts(
            line
            for part in parts
            for line in part.get("matched_lines", []) or []
        )
        merged["match_count"] = len(merged["matched_lines"])
        return merged

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

    @classmethod
    def _chronological_result_sort_key(cls, result: dict) -> tuple:
        metadata = result.get("metadata", {})
        story_key = cls._story_time_sort_key(metadata)
        if story_key is not None:
            return (0, story_key, result.get("chunk_id", ""))
        return (1, cls._result_sort_key(result), result.get("chunk_id", ""))

    @staticmethod
    def _story_time_sort_key(meta: dict) -> tuple | None:
        knowledge_type = meta.get("knowledge_type")
        if knowledge_type not in {"main_story", "side_story"}:
            return None

        path = meta.get("path", "")
        path_obj = Path(path)
        filename = path_obj.name
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
