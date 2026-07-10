from __future__ import annotations

import argparse
import json

from icpquery_mcp import __version__
from icpquery_mcp.tools import local_tools


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="icpquery", description="ICPQuery-MCP 的本地辅助 CLI。")
    parser.add_argument("-c", "--config", default="", help="配置文件路径，默认读取环境变量和内置默认值。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query = subparsers.add_parser("query", help="单条 ICP 备案查询。")
    query.add_argument("name", nargs="?", default="", help="查询关键词：公司名、域名、备案号或 App 名。")
    query.add_argument("-n", "--name", dest="name_flag", default="", help="查询关键词。")
    query.add_argument("-t", "--type", default="web", help="web|app|mapp|kapp|bweb|bapp|bmapp|bkapp")
    query.add_argument("--page", type=int, default=1)
    query.add_argument("--page-size", "--size", type=int, default=26)
    query.add_argument("--proxy", default="")

    config = subparsers.add_parser("config-show", help="显示当前配置。")
    config.set_defaults(config_show=True)

    env = subparsers.add_parser("check-env", help="检查运行环境。")
    env.set_defaults(check_env=True)

    version = subparsers.add_parser("version", help="显示版本。")
    version.set_defaults(version=True)

    args = parser.parse_args(argv)
    config_path = args.config or None

    if args.command == "query":
        name = args.name_flag or args.name
        if not name:
            raise SystemExit("请提供查询内容，例如：icpquery query baidu.com")
        if args.type.startswith("b"):
            data = local_tools.icp_blacklist(name, args.type, args.proxy, config_path)
        else:
            data = local_tools.icp_query(name, args.type, args.page, args.page_size, args.proxy, config_path)
        _print_json(data)
    elif args.command == "config-show":
        _print_json(local_tools.show_config(config_path))
    elif args.command == "check-env":
        _print_json(local_tools.check_environment(config_path))
    elif args.command == "version":
        print(__version__)


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
