"""
Entrypoint for building the EduSync backend into a single executable.

This script:
- Creates and runs the Flask app using Waitress (with a fallback to Flask dev server)
- Configures dual logging (to file + console)
- Handles PyInstaller onefile resource extraction (_MEIPASS)
"""

import logging
import os
import sys
from app import create_app
from config import Config


def resource_path(relative_path):
    """
    Return absolute path to resource.
    PyInstaller extracts files to a temporary folder stored in sys._MEIPASS when in onefile mode.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


def setup_logging():
    """Set up safe file + console logging."""
    try:
        # Prefer to store logs beside the executable
        log_dir = os.path.dirname(resource_path(""))

        # Fallback to user AppData or ~/.config if not writable
        if not os.access(log_dir, os.W_OK):
            raise PermissionError
    except Exception:
        log_dir = os.path.join(
            os.getenv("APPDATA", os.path.expanduser("~/.config")), "EduSync_SMS", "logs"
        )
        os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "edusync_backend.log")

    # Configure logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logging.info("===== Starting EduSync Backend =====")
    logging.info(f"Python executable: {sys.executable}")
    logging.info(f"Base path: {resource_path('')}")
    logging.info(f"Running in frozen mode: {getattr(sys, 'frozen', False)}")
    logging.info(f"Log file: {log_file}")

    return logger


def main():
    logger = setup_logging()

    app = create_app()
    host = Config.HOST
    port = Config.PORT

    try:
        from waitress import serve

        logger.info(f"Serving EduSync on http://{host}:{port}")
        serve(app, host=host, port=port, threads=4)
    except Exception:
        logger.exception(
            "Waitress not available or failed — falling back to Flask Dev Server"
        )
        app.run(host=host, port=port)


if __name__ == "__main__":
    main()
