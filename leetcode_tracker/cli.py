"""leetcode-tracker CLI 入口。"""

from __future__ import annotations

import argparse
import sys

from leetcode_tracker import __version__
from leetcode_tracker.db import init_db
from leetcode_tracker.report import write_today_report
from leetcode_tracker.server import DEFAULT_HOST, DEFAULT_PORT, run_server
from leetcode_tracker.stats import format_stats_text, get_overview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leetcode-tracker",
        description="完全本地的力扣刷题追踪助手",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="启动本机桥接服务")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)

    sub.add_parser("stats", help="打印刷题统计概览")

    report = sub.add_parser("report", help="生成 Markdown 日报")
    report.add_argument(
        "--today",
        action="store_true",
        help="生成今日日报（当前 MVP 仅支持该模式）",
    )
    return parser


def cmd_serve(args: argparse.Namespace) -> int:
    run_server(host=args.host, port=args.port)
    return 0


def cmd_stats(_: argparse.Namespace) -> int:
    conn = init_db()
    try:
        stats = get_overview(conn)
        sys.stdout.write(format_stats_text(stats))
    finally:
        conn.close()
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    if not args.today:
        print("请使用: leetcode-tracker report --today", file=sys.stderr)
        return 2
    path = write_today_report()
    print(f"Wrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        return cmd_serve(args)
    if args.command == "stats":
        return cmd_stats(args)
    if args.command == "report":
        return cmd_report(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
