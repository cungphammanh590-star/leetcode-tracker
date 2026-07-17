"""知识图谱进度与陪练上下文查询。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class NodePlacement:
    node_id: str
    track_id: str
    track_name: str
    submodule_name: str
    sort_order: int
    annotation: str | None
    total_in_node: int
    accepted_in_node: int
    acceptance_rate: float
    avg_struggle: float
    last_submitted_at: str | None


def _node_progress(
    conn: sqlite3.Connection, node_id: str
) -> tuple[int, int, float, float, str | None]:
    rows = conn.execute(
        """
        SELECT knp.problem_id, ps.accepted_count, ps.struggle_score, ps.last_submitted_at
        FROM kg_node_problems knp
        LEFT JOIN problem_stats ps ON ps.problem_id = knp.problem_id
        WHERE knp.node_id = ?
        """,
        (node_id,),
    ).fetchall()
    total = len(rows)
    accepted = sum(1 for r in rows if r["accepted_count"] and int(r["accepted_count"]) > 0)
    rate = (accepted / total) if total else 0.0
    struggles = [
        float(r["struggle_score"])
        for r in rows
        if r["struggle_score"] is not None
    ]
    avg_struggle = sum(struggles) / len(struggles) if struggles else 0.0
    last_times = [str(r["last_submitted_at"]) for r in rows if r["last_submitted_at"]]
    last_submitted = max(last_times) if last_times else None
    return total, accepted, rate, avg_struggle, last_submitted


def list_placements_for_problem(
    conn: sqlite3.Connection, problem_id: int
) -> list[NodePlacement]:
    rows = conn.execute(
        """
        SELECT knp.node_id, knp.sort_order, knp.annotation,
               kn.id AS node_pk, kn.track_id, kn.name AS submodule_name,
               kt.name AS track_name
        FROM kg_node_problems knp
        JOIN kg_nodes kn ON kn.id = knp.node_id
        JOIN kg_tracks kt ON kt.id = kn.track_id
        WHERE knp.problem_id = ?
        ORDER BY kt.sort_order, kn.sort_order, knp.sort_order
        """,
        (problem_id,),
    ).fetchall()
    placements: list[NodePlacement] = []
    for row in rows:
        total, accepted, rate, avg_struggle, last_sub = _node_progress(conn, row["node_id"])
        placements.append(
            NodePlacement(
                node_id=row["node_id"],
                track_id=row["track_id"],
                track_name=row["track_name"],
                submodule_name=row["submodule_name"],
                sort_order=int(row["sort_order"]),
                annotation=row["annotation"],
                total_in_node=total,
                accepted_in_node=accepted,
                acceptance_rate=rate,
                avg_struggle=avg_struggle,
                last_submitted_at=last_sub,
            )
        )
    return placements


def _recency_ts(dt_str: Optional[str]) -> float:
    if not dt_str:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(dt_str)[:19]).timestamp()
    except ValueError:
        return 0.0


def select_primary_placement(placements: list[NodePlacement]) -> NodePlacement | None:
    """B+C：最弱 node 优先，平局取最近活跃 track。"""
    if not placements:
        return None
    return min(
        placements,
        key=lambda p: (
            p.acceptance_rate,
            -_recency_ts(p.last_submitted_at),
            p.track_id,
        ),
    )


def get_predecessors_in_node(
    conn: sqlite3.Connection, node_id: str, problem_id: int, *, limit: int = 5
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT knp.problem_id, knp.sort_order, knp.annotation,
               ps.accepted_count, ps.last_status, p.title
        FROM kg_node_problems knp
        LEFT JOIN problem_stats ps ON ps.problem_id = knp.problem_id
        LEFT JOIN problems p ON p.problem_id = knp.problem_id
        WHERE knp.node_id = ? AND knp.sort_order < (
            SELECT sort_order FROM kg_node_problems
            WHERE node_id = ? AND problem_id = ?
        )
        ORDER BY knp.sort_order DESC
        LIMIT ?
        """,
        (node_id, node_id, problem_id, limit),
    ).fetchall()
    result = []
    for row in reversed(rows):
        ac = int(row["accepted_count"] or 0) > 0
        title = row["title"] or f"#{row['problem_id']}"
        result.append(
            {
                "problem_id": row["problem_id"],
                "title": title,
                "accepted": ac,
                "last_status": row["last_status"],
                "annotation": row["annotation"],
            }
        )
    return result


def format_kg_context_markdown(
    conn: sqlite3.Connection, problem_id: int
) -> tuple[str, NodePlacement | None]:
    placements = list_placements_for_problem(conn, problem_id)
    primary = select_primary_placement(placements)
    if primary is None:
        return "（该题不在 algorithm-stone 知识图谱内）", None

    preds = get_predecessors_in_node(conn, primary.node_id, problem_id)
    pred_lines = []
    for item in preds:
        mark = "✅" if item["accepted"] else "❌"
        ann = f"（{item['annotation']}）" if item.get("annotation") else ""
        pred_lines.append(
            f"- {mark} {item['problem_id']}. {item['title']}{ann}"
        )
    if not pred_lines:
        pred_lines.append("- （无前置题或本题位于子模块首位）")

    other_tracks = [
        p for p in placements if p.node_id != primary.node_id
    ]
    other_line = ""
    if other_tracks:
        bits = [
            f"{p.track_name}/{p.submodule_name}"
            for p in other_tracks[:3]
        ]
        other_line = f"\n- 亦属其他路线：{', '.join(bits)}"

    ann = f"（标注：{primary.annotation}）" if primary.annotation else ""
    md = f"""## 图谱位置
- 路线：{primary.track_name} → 子模块：{primary.submodule_name}
- 本题序位：第 {primary.sort_order} 题{ann}
- 子模块进度：{primary.accepted_in_node}/{primary.total_in_node} AC（{primary.acceptance_rate:.0%}）
- 子模块平均挣扎指数：{primary.avg_struggle:.2f}{other_line}

## 前序题（同子模块）
{chr(10).join(pred_lines)}
"""
    return md, primary


def list_track_progress(conn: sqlite3.Connection, track_id: str | None = None) -> list[dict[str, Any]]:
    if track_id:
        tracks = conn.execute(
            "SELECT id, name FROM kg_tracks WHERE id = ? ORDER BY sort_order",
            (track_id,),
        ).fetchall()
    else:
        tracks = conn.execute(
            "SELECT id, name FROM kg_tracks ORDER BY sort_order"
        ).fetchall()

    result: list[dict[str, Any]] = []
    for track in tracks:
        nodes = conn.execute(
            """
            SELECT id, name, sort_order FROM kg_nodes
            WHERE track_id = ? ORDER BY sort_order
            """,
            (track["id"],),
        ).fetchall()
        node_rows = []
        for node in nodes:
            total, accepted, rate, avg_struggle, _ = _node_progress(conn, node["id"])
            node_rows.append(
                {
                    "node_id": node["id"],
                    "name": node["name"],
                    "total": total,
                    "accepted": accepted,
                    "acceptance_rate": round(rate, 4),
                    "avg_struggle": round(avg_struggle, 2),
                }
            )
        result.append(
            {
                "track_id": track["id"],
                "track_name": track["name"],
                "nodes": node_rows,
            }
        )
    return result
