"""解析 algorithm-stone map 文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedProblem:
    problem_id: int
    annotation: str | None = None


@dataclass
class ParsedNode:
    track_name: str
    submodule_name: str
    problems: list[ParsedProblem] = field(default_factory=list)
    sort_order: int = 0


@dataclass
class ParsedTrack:
    track_id: str
    track_name: str
    nodes: list[ParsedNode] = field(default_factory=list)


_ANNOTATION_RE = re.compile(r"\(([^)]+)\)")


def _strip_annotations(segment: str) -> tuple[str, str | None]:
    annotations = _ANNOTATION_RE.findall(segment)
    cleaned = _ANNOTATION_RE.sub("", segment)
    annotation = ",".join(a.strip() for a in annotations) if annotations else None
    return cleaned, annotation


def _parse_problem_token(token: str) -> ParsedProblem | None:
    token = token.strip()
    if not token:
        return None
    cleaned, annotation = _strip_annotations(token)
    match = re.search(r"\b(\d+)\b", cleaned)
    if not match:
        return None
    return ParsedProblem(problem_id=int(match.group(1)), annotation=annotation)


def parse_map_text(text: str, *, track_id: str, track_name: str) -> ParsedTrack:
    track = ParsedTrack(track_id=track_id, track_name=track_name)
    current_root: str | None = None
    node_order = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            inner = line[1 : line.index("]")].strip()
            if inner.startswith("-"):
                submodule = inner[1:].strip()
                node_order += 1
                track.nodes.append(
                    ParsedNode(
                        track_name=current_root or track_name,
                        submodule_name=submodule,
                        sort_order=node_order,
                    )
                )
            else:
                current_root = inner
            continue

        if not track.nodes:
            continue
        node = track.nodes[-1]
        parts = re.split(r"[\s,，、]+", line)
        for part in parts:
            parsed = _parse_problem_token(part)
            if parsed is not None:
                node.problems.append(parsed)

    return track


def parse_map_file(path: Path, *, track_id: str | None = None) -> ParsedTrack:
    stem = path.stem
    if track_id is None:
        track_id = stem.replace("leetcode-", "", 1) if stem.startswith("leetcode-") else stem
    text = path.read_text(encoding="utf-8")
    track_name = track_id
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and not line.startswith("[-") and "]" in line:
            track_name = line[1 : line.index("]")].strip()
            break
    return parse_map_text(text, track_id=track_id, track_name=track_name)


def bundled_maps_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "algorithm_stone" / "maps"
