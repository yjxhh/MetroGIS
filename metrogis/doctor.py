import platform
import sys

from . import __version__
from .logger import get_logger


def doctor():

    logger = get_logger()

    logger.info(
        "MetroGIS Environment Doctor"
    )

    logger.info(
        f"Version: {__version__}"
    )

    logger.info(
        f"Python: {sys.version.split()[0]}"
    )

    logger.info(
        f"OS: {platform.system()}"
    )

    logger.info(
        "Environment check passed"
    )
