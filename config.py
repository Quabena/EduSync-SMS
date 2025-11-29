import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE reading environment variables
load_dotenv()

APP_NAME = "EduSync SMS"

# --- BASE APP DIR (cross-platform) ---
if os.name == "nt":  # Windows (APPDATA)
    appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    BASE_DIR = Path(appdata) / APP_NAME
else:
    BASE_DIR = Path.home() / ".config" / APP_NAME

BASE_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """Production-safe Flask configuration"""

    # --- CORE SETTINGS ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

    # --- DATABASE ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'edusync.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- DEFAULT ADMIN ACCOUNT ---
    DEFAULT_ADMIN_USER = os.environ.get("EDUSYNC_ADMIN_USER", "")
    DEFAULT_ADMIN_EMAIL = os.environ.get("EDUSYNC_ADMIN_EMAIL", "")
    DEFAULT_ADMIN_PASS = os.environ.get("EDUSYNC_ADMIN_PASS", "")

    # --- STORAGE DIRECTORIES (fallbacks only used if .env does NOT define them) ---
    BACKUP_DIR = Path(os.environ.get("BACKUP_DIR") or (BASE_DIR / "backups"))
    DOCUMENT_DIR = Path(os.environ.get("DOCUMENT_DIR") or (BASE_DIR / "student_photos"))
    TEACHER_PHOTOS_DIR = Path(
        os.environ.get("TEACHER_PHOTOS_DIR") or (BASE_DIR / "teacher_photos")
    )
    TEACHER_CERTS_DIR = Path(
        os.environ.get("TEACHER_CERTS_DIR") or (BASE_DIR / "teacher_certificates")
    )
    QR_DIR = Path(os.environ.get("QR_DIR") or (BASE_DIR / "qr_storage"))
    REPORT_DIR = Path(os.environ.get("REPORT_DIR") or (BASE_DIR / "reports"))

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))

    # Allow electron frontend to communicate CORS-free
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
