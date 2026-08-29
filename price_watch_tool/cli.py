"""命令行入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .core import PLATFORM_LABELS, collect_price_data, export_result_files
from .web import run_demo_server


def _platforms_argument(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("platforms 不能为空")
    invalid = [item for item in items if item not in PLATFORM_LABELS]
    if invalid:
        raise argparse.ArgumentTypeError(f"不支持的平台: {', '.join(invalid)}")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="price-watch",
        description="电商商品价格自动化采集与横向对比工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="执行一次采集并生成结果文件")
    collect_parser.add_argument("--keyword", required=True, help="搜索关键词")
    collect_parser.add_argument(
        "--platforms",
        type=_platforms_argument,
        default=list(PLATFORM_LABELS.keys()),
        help="逗号分隔的平台列表，默认 jd,taobao,pdd",
    )
    collect_parser.add_argument("--limit", type=int, default=4, help="每个平台采集条数")
    collect_parser.add_argument(
        "--mode",
        choices=["sample", "live"],
        default="sample",
        help="采集模式，默认 sample",
    )
    collect_parser.add_argument(
        "--output-dir",
        default="price_watch_output",
        help="输出目录，默认 ./price_watch_output",
    )
    collect_parser.add_argument(
        "--print-json",
        action="store_true",
        help="同时将结果打印到标准输出",
    )

    serve_parser = subparsers.add_parser("serve", help="启动演示网页")
    serve_parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    serve_parser.add_argument("--port", type=int, default=8765, help="监听端口")
    serve_parser.add_argument(
        "--keyword",
        default="蓝牙耳机",
        help="网页初始化时展示的示例关键词",
    )
    serve_parser.add_argument(
        "--mode",
        choices=["sample", "live"],
        default="sample",
        help="网页默认采集模式",
    )
    serve_parser.add_argument("--limit", type=int, default=4, help="每个平台默认采集条数")

    return parser


def run_collect(args: argparse.Namespace) -> int:
    payload = collect_price_data(
        keyword=args.keyword,
        platforms=args.platforms,
        limit=args.limit,
        mode=args.mode,
    )
    output_dir = Path(args.output_dir)
    paths = export_result_files(payload, output_dir=output_dir)

    print(f"关键词: {payload['keyword']}")
    print(f"模式: {payload['mode']}")
    print(f"结果条数: {len(payload['items'])}")
    print("输出文件:")
    print(f"  JSON: {paths['json']}")
    print(f"  CSV : {paths['csv']}")
    print(f"  HTML: {paths['html']}")
    if payload["warnings"]:
        print("提示:")
        for warning in payload["warnings"]:
            print(f"  - {warning}")
    if args.print_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_serve(args: argparse.Namespace) -> int:
    run_demo_server(
        host=args.host,
        port=args.port,
        initial_keyword=args.keyword,
        default_mode=args.mode,
        default_limit=args.limit,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        return run_collect(args)
    if args.command == "serve":
        return run_serve(args)
    parser.error(f"未知子命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
