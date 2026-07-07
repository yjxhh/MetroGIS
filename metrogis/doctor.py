import platform
import sys

from . import __version__


def doctor():

    print("=" * 40)

    print(" MetroGIS Environment Doctor")

    print("=" * 40)

    print(f"Version : {__version__}")

    print(f"Python  : {sys.version.split()[0]}")

    print(f"OS      : {platform.system()}")

    print()

    print("Status  : READY")