import argparse

from .doctor import doctor


def main():

    parser = argparse.ArgumentParser(
        prog="metrogis",
        description="MetroGIS CLI"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor")

    args = parser.parse_args()

    if args.command == "doctor":

        doctor()

    else:

        parser.print_help()