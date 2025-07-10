import os
from pathlib import Path


class Config:
    # Secret key
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or "43cba8188f13db93ab9b2f57d569b7c3b6ca59a6b2fcb623c6988be6e527a9b3"
    )

    # Base local storage path
    BASE_DIR = Path.home() / "Documents" / "EduSync-SMS" / "Local_Storage"

    # Database path
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'namongsdajhs.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File storage paths (leave as Path objects)
    BACKUP_DIR = BASE_DIR / "backups"
    DOCUMENT_DIR = BASE_DIR / "student_photos"
    QR_DIR = BASE_DIR / "qr_storage"
    REPORT_DIR = BASE_DIR / "reports"

    # PyInstaller flag
    BUNDLE_MODE = os.environ.get("BUNDLE_MODE", False)
