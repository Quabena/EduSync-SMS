import os
from pathlib import Path

APP_NAME = "EduSync SMS"

# Cross-platform app data directory
if os.name == "nt":  # Windows
    appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    BASE_DIR = Path(appdata) / APP_NAME
else:
    BASE_DIR = Path.home() / ".config" / APP_NAME


BASE_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """SAFE CONFIG — production secrets loaded from .env"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-key-change-me")
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'edusync.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Default admin values (only used if no admin exists)
    DEFAULT_ADMIN_USER = os.environ.get("EDUSYNC_ADMIN_USER", "")
    DEFAULT_ADMIN_EMAIL = os.environ.get("EDUSYNC_ADMIN_EMAIL", "")
    DEFAULT_ADMIN_PASS = os.environ.get("EDUSYNC_ADMIN_PASS", "")

    # Storage directories
    BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", BASE_DIR / "backups"))
    DOCUMENT_DIR = Path(os.environ.get("DOCUMENT_DIR", BASE_DIR / "student_photos"))
    TEACHER_PHOTOS_DIR = Path(
        os.environ.get("TEACHER_PHOTOS_DIR", BASE_DIR / "teacher_photos")
    )
    TEACHER_CERTS_DIR = Path(
        os.environ.get("TEACHER_CERTS_DIR", BASE_DIR / "teacher_certificates")
    )
    QR_DIR = Path(os.environ.get("QR_DIR", BASE_DIR / "qr_storage"))
    REPORT_DIR = Path(os.environ.get("REPORT_DIR", BASE_DIR / "reports"))
