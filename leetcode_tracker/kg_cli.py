"""kg / coach CLI 子命令。"""

from __future__ import annotations

import argparse
import sys

from leetcode_tracker.coach_deps import coach_dependencies_available, coach_import_error_message
from leetcode_tracker.db import init_db
from leetcode_tracker.kg.import_maps import get_kg_status, import_maps
from leetcode_tracker.kg.queries import format_kg_context_markdown, list_track_progress
from leetcode_tracker.problem_stats import ensure_stats_materialized


def register_kg_parser(sub: argparse._SubParsersAction) -> None:
    kg = sub.add_parser("kg", help="知识图谱（algorithm-stone）")
    kg_sub = kg.add_subparsers(dest="kg_command", required=True)
    kg_sub.add_parser("import", help="从 bundled map 导入图谱")
    kg_sub.add_parser("status", help="查看图谱导入状态")
    prog = kg_sub.add_parser("progress", help="按路线查看子模块进度")
    prog.add_argument("--track", default=None, help="路线 id，如 dp")
    ctx = kg_sub.add_parser("context", help="输出单题图谱上下文（Markdown）")
    ctx.add_argument("problem_id", type=int)


def register_coach_parser(sub: argparse._SubParsersAction) -> None:
    coach = sub.add_parser("coach", help="刷题陪练（需 [coach] 依赖）")
    coach_sub = coach.add_subparsers(dest="coach_command", required=True)
    follow = coach_sub.add_parser("follow", help="围绕单次提交陪练")
    follow.add_argument("submission_id")
    coach_sub.add_parser("debrief", help="今日复盘开场")
    chat = coach_sub.add_parser("chat", help="交互式陪练（需 submission_id）")
    chat.add_argument("submission_id")


def cmd_kg(args: argparse.Namespace) -> int:
    conn = init_db()
    try:
        if args.kg_command == "import":
            result = import_maps(conn)
            print(
                f"Imported {result['tracks']} tracks, "
                f"{result['nodes']} nodes, "
                f"{result['problems']} problems, "
                f"{result['edges']} edges"
            )
            return 0
        if args.kg_command == "status":
            import json

            print(json.dumps(get_kg_status(conn), ensure_ascii=False, indent=2))
            return 0
        if args.kg_command == "progress":
            ensure_stats_materialized(conn)
            rows = list_track_progress(conn, args.track)
            for track in rows:
                print(f"\n## {track['track_name']} ({track['track_id']})")
                for node in track["nodes"]:
                    print(
                        f"  - {node['name']}: {node['accepted']}/{node['total']} AC "
                        f"({node['acceptance_rate']:.0%}), struggle≈{node['avg_struggle']}"
                    )
            return 0
        if args.kg_command == "context":
            ensure_stats_materialized(conn)
            md, _ = format_kg_context_markdown(conn, args.problem_id)
            sys.stdout.write(md)
            if not md.endswith("\n"):
                sys.stdout.write("\n")
            return 0
    finally:
        conn.close()
    return 2


def cmd_coach(args: argparse.Namespace) -> int:
    if not coach_dependencies_available():
        print(coach_import_error_message(), file=sys.stderr)
        return 2
    from leetcode_tracker.coach import service as coach_service

    conn = init_db()
    try:
        ensure_stats_materialized(conn)
        if args.coach_command == "debrief":
            print(coach_service.debrief_today(conn))
            return 0
        if args.coach_command == "follow":
            result = coach_service.engage(conn, args.submission_id)
            print(result["opening"])
            print(f"\n[session_id={result['session_id']}]")
            return 0
        if args.coach_command == "chat":
            result = coach_service.engage(conn, args.submission_id)
            print(result["opening"])
            print(f"\n[session_id={result['session_id']}] 输入消息，空行或 Ctrl-D 结束。\n")
            session_id = result["session_id"]
            while True:
                try:
                    line = input("你> ").strip()
                except EOFError:
                    break
                if not line:
                    break
                reply = coach_service.chat(conn, session_id, line)
                print(f"\n陪练> {reply['reply']}\n")
                if reply.get("done"):
                    break
            return 0
    finally:
        conn.close()
    return 2
