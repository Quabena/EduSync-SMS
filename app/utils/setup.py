import os
from pathlib import Path
from flask import current_app


def create_storage_dirs(app):
    """Creating all required storage directories"""
    with app.app_context():
        dirs = [
            app.config["BACKUP_DIR"],
            app.config["DOCUMENT_DIR"],
            app.config["QR_DIR"],
            app.config["REPORT_DIR"],
        ]

        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)

        # Creating Initial placeholder files
        (app.config["DOCUMENT_DIR"] / "placeholder.txt").touch()
        (app.config["QR_DIR"] / "placeholder.txt").touch()
        (app.config["REPORT_DIR"] / "placeholder.txt").touch()
