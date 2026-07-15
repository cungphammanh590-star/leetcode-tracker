"""Markdown 日报生成。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from leetcode_tracker.db import init_db
from leetcode_tracker.paths import ensure_dir, report_dir
from leetcode_tracker.stats import OverviewStats, get_overview


def _status_mark(status: str) -> str:
    return "✅" if status == "Accepted" else "❌"


def render_daily_markdown(stats: OverviewStats, day: str) -> str:
    lines = [
        f"# 力扣刷题日报 - {day}",
        "",
        "## 今日概览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 今日提交 | {stats.today_submissions} 次 |",
        f"| 今日通过 | {stats.today_accepted} 次 |",
        f"| 今日通过率 | {stats.today_acceptance_rate}% |",
        f"| 累计提交 | {stats.total_submissions} 次 |",
        f"| 累计通过 | {stats.accepted_count} 次 |",
        f"| 累计通过率 | {stats.acceptance_rate}% |",
        f"| 连续打卡 | {stats.streak_days} 天 |",
        "",
        "## 今日题目",
        "",
        "| 题目 | 难度 | 状态 | 用时 |",
        "|------|------|------|------|",
    ]
    if not stats.today_items:
        lines.append("| （今日暂无提交） | - | - | - |")
    else:
        for item in stats.today_items:
            runtime = f"{item['runtime_ms']}ms" if item["runtime_ms"] is not None else "-"
            title = f"{item['problem_id']}. {item['title']}"
            diff = item["difficulty"] or "-"
            status = f"{_status_mark(item['status'])} {item['status']}"
            lines.append(f"| {title} | {diff} | {status} | {runtime} |")

    lines.extend(
        [
            "",
            "## 继续保持",
            "",
            f"连续打卡 {stats.streak_days} 天。用 `leetcode-tracker stats` 可随时查看累计进度。",
            "",
        ]
    )
    return "\n".join(lines)


def write_today_report(output_dir: Path | None = None) -> Path:
    day = datetime.now().astimezone().date().isoformat()
    target_dir = output_dir or report_dir()
    ensure_dir(target_dir)
    path = target_dir / f"{day}.md"

    conn = init_db()
    try:
        stats = get_overview(conn)
        path.write_text(render_daily_markdown(stats, day), encoding="utf-8")
    finally:
        conn.close()
    return path
