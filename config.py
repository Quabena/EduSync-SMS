import os
from pathlib import Path


class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or "43cba8188f13db93ab9b2f57d569b7c3b6ca59a6b2fcb623c6988be6e527a9b3"
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///" + str(
        Path.cwd() / "local_storage" / "namongsdajhs.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Offline storage paths
    BACKUP_DIR = Path.cwd() / "local_storage" / "backups"
    DOCUMENT_DIR = Path.cwd() / "local_storage" / "documents"
    QR_DIR = Path.cwd() / "local_storage" / "qr_storage"
    REPORT_DIR = Path.cwd() / "local_storage" / "reports"

    # PyInstaller config
    BUNDLE_MODE = os.environ.get("BUNDLE_MODE", False)
