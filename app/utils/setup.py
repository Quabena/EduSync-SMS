from pathlib import Path


def create_storage_dirs(app):
    """Create required directories and placeholder files."""
    with app.app_context():
        storage_keys = [
            "BACKUP_DIR",
            "DOCUMENT_DIR",
            "TEACHER_PHOTOS_DIR",
            "TEACHER_CERTS_DIR",
            "QR_DIR",
            "REPORT_DIR",
        ]

        for key in storage_keys:
            directory = app.config.get(key)
            # Accept either Path or string (coerce to Path)
            if directory is None:
                continue
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            # create placeholder to keep dir in VCS
            (directory / "placeholder.txt").touch(exist_ok=True)
