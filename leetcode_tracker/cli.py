"""leetcode-tracker CLI 入口。"""

from __future__ import annotations

import argparse
import json
import sys

from leetcode_tracker import __version__
from leetcode_tracker.app import run_app
from leetcode_tracker.autostart import install_autostart, uninstall_autostart
from leetcode_tracker.config import DEFAULTS, load_config, set_config_value
from leetcode_tracker.db import init_db
from leetcode_tracker.paths import db_path
from leetcode_tracker.report import write_today_report
from leetcode_tracker.server import run_server
from leetcode_tracker.stats import format_stats_text, get_overview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leetcode-tracker",
        description="完全本地的力扣刷题追踪助手（仅 leetcode.cn）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="启动本机桥接服务与仪表盘")
    serve.add_argument("--host", default=None, help="默认读配置")
    serve.add_argument("--port", type=int, default=None, help="默认读配置")

    sub.add_parser("stats", help="打印刷题统计概览")
    sub.add_parser("app", help="用 pywebview 打开桌面仪表盘")

    report = sub.add_parser("report", help="生成 Markdown 日报")
    report.add_argument("--today", action="store_true", help="生成今日日报")

    config_p = sub.add_parser("config", help="查看或修改本机配置")
    config_sub = config_p.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="显示当前配置")
    config_set = config_sub.add_parser("set", help="设置配置项")
    config_set.add_argument("key", choices=sorted(DEFAULTS.keys()))
    config_set.add_argument("value")

    auto = sub.add_parser("autostart", help="macOS 开机自启 serve")
    auto_sub = auto.add_subparsers(dest="autostart_command", required=True)
    auto_sub.add_parser("install", help="安装 LaunchAgent")
    auto_sub.add_parser("uninstall", help="卸载 LaunchAgent")
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


def cmd_config(args: argparse.Namespace) -> int:
    if args.config_command == "show":
        cfg = load_config()
        payload = dict(cfg)
        payload["db_path_readonly"] = str(db_path())
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.config_command == "set":
        try:
            cfg = set_config_value(args.key, args.value)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0
    return 2


def cmd_autostart(args: argparse.Namespace) -> int:
    if args.autostart_command == "install":
        path = install_autostart()
        print(f"Installed LaunchAgent: {path}")
        return 0
    if args.autostart_command == "uninstall":
        uninstall_autostart()
        print("Uninstalled LaunchAgent (if present)")
        return 0
    return 2


def cmd_app(_: argparse.Namespace) -> int:
    return run_app()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "serve": cmd_serve,
        "stats": cmd_stats,
        "report": cmd_report,
        "config": cmd_config,
        "autostart": cmd_autostart,
        "app": cmd_app,
    }
    handler = dispatch.get(args.command)
    if not handler:
        parser.error(f"unknown command: {args.command}")
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
