"""
Entrypoint for building the backend into a single executable

This script:
- creates the Flask App
- starts a WSGI server (waitress)
- logs basic info
- uses a hard-cded host/port from run.py
"""

import logging
import os
import sys
import time

from app import create_app
from config import Config


def resource_path(relative_path):
    """
    Return absolute path to resource.
    PyInstaller extracts files to a temporary folder stored in sys._MEIMPASS when in onefile mode
    """

    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


def main():
    # Setting up logging file for troubleshooting
    log_dir = os.path.dirname(resource_path(""))
    log_file = os.path.join(log_dir, "edusync_backend.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.info("Starting EduSync")

    app = create_app()

    host = Config.HOST
    port = Config.PORT

    try:
        # Using waitress (producion grade for windows)
        from waitress import serve

        logging.info(f"Serving on http://{host}:{port}")
        serve(app, host=host, port=port, threads=4)
    except Exception:
        # Falling back on Flask Dev Server if waitress isn't available
        logging.exception(
            "Waitress not available or failed, falling back to Falsk Dev Server"
        )
        app.run(host=host, port=port)


if __name__ == "__main__":
    main()
