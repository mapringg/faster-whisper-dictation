#!/usr/bin/env python3
import logging
import sys

from src.cli import parse_args
from src.core.app import App

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/tmp/dictation.log")],
)
logger = logging.getLogger(__name__)


def main():
    try:
        args = parse_args()
        app = App(args)
        app.run()
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
