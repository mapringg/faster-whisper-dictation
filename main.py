#!/usr/bin/env python3
import logging
import os
import sys
from pathlib import Path

from src.cli import parse_args
from src.core.app import App
from src.core.utils import load_env_from_file

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/tmp/dictation.log")],
)
logger = logging.getLogger(__name__)


def main():
    # Load environment variables. Project-level .env overrides home-level .env
    load_env_from_file(os.path.join(str(Path.home()), ".env"))
    project_env = Path(__file__).resolve().parent / ".env"
    load_env_from_file(project_env)

    try:
        args = parse_args()
        app = App(args)
        app.run()
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
