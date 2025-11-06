import os
from pathlib import Path

APP_NAME = "EduSync SMS"

# Cross-platform app data directory
if os.name == "nt":  # Windows
    BASE_DIR = Path(os.getenv("APPDATA")) / APP_NAME  # type:ignore
elif os.name == "posix":
    BASE_DIR = Path.home() / ".config" / APP_NAME
else:
    BASE_DIR = Path.home() / APP_NAME

BASE_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or "43cba8188f13db93ab9b2f57d569b7c3b6ca59a6b2fcb623c6988be6e527a9b3"
    )

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'edusync.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    HOST = "127.0.0.1"
    PORT = 5000
    DEBUG = False

    BACKUP_DIR = BASE_DIR / "backups"
    DOCUMENT_DIR = BASE_DIR / "student_photos"
    TEACHER_PHOTOS_DIR = BASE_DIR / "teacher_photos"
    TEACHER_CERTS_DIR = BASE_DIR / "teacher_certificates"
    QR_DIR = BASE_DIR / "qr_storage"
    REPORT_DIR = BASE_DIR / "reports"
