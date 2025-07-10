from pathlib import Path


def create_storage_dirs(app):
    """Create required directories and placeholder files."""
    with app.app_context():
        for key in ["BACKUP_DIR", "DOCUMENT_DIR", "QR_DIR", "REPORT_DIR"]:
            directory = app.config[key]
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "placeholder.txt").touch(exist_ok=True)
