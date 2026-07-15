"""
MetroGIS CLI
"""

import argparse

from .doctor import doctor

from .commands.download import (
    download_command
)


def main():

    parser = argparse.ArgumentParser(
        prog="metrogis",
        description="MetroGIS CLI"
    )

    subparsers = parser.add_subparsers(
        dest="command"
    )

    #
    # doctor
    #

    subparsers.add_parser(

        "doctor",

        help="检查运行环境"

    )

    #
    # download
    #

    download = subparsers.add_parser(

        "download",

        help="下载指定城市地铁线路"

    )

    download.add_argument(

        "--city",

        required=True,

        help="城市名称，例如：北京"

    )

    download.add_argument(

        "--line",

        required=True,

        help="线路名称，例如：10号线"

    )

    #
    # list（预留）
    #

    list_cmd = subparsers.add_parser(

        "list",

        help="列出指定城市所有线路（开发中）"

    )

    list_cmd.add_argument(

        "--city",

        required=True,

        help="城市名称"

    )

    #
    # export-track（预留）
    #

    export = subparsers.add_parser(

        "export-track",

        help="导出线路轨迹（开发中）"

    )

    export.add_argument(

        "--city",

        required=True

    )

    export.add_argument(

        "--line",

        required=True

    )

    export.add_argument(

        "--start",

        required=True

    )

    export.add_argument(

        "--end",

        required=True

    )

    export.add_argument(

        "--step",

        type=int,

        default=50,

        help="采样间隔（米）"

    )

    args = parser.parse_args()

    #
    # doctor
    #

    if args.command == "doctor":

        doctor()

    #
    # download
    #

    elif args.command == "download":

        download_command(

            city=args.city,

            line=args.line

        )

    #
    # list
    #

    elif args.command == "list":

        print(

            "list 命令开发中..."

        )

    #
    # export-track
    #

    elif args.command == "export-track":

        print(

            "export-track 命令开发中..."

        )

    else:

        parser.print_help()


if __name__ == "__main__":

    main()