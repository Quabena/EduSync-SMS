import os
from pathlib import Path


BASE_DIR = Path.home() / "Documents" / "EduSync-SMS" / "Local_Storage"


class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or "43cba8188f13db93ab9b2f57d569b7c3b6ca59a6b2fcb623c6988be6e527a9b3"
    )

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or f"sqlite:///{(BASE_DIR / 'namongsdajhs.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # storage locations (Path objects — code will accept strings too)
    BACKUP_DIR = BASE_DIR / "backups"
    DOCUMENT_DIR = BASE_DIR / "student_photos"  # where student photos live
    TEACHER_PHOTOS_DIR = BASE_DIR / "teacher_photos"  # where teacher photos live
    TEACHER_CERTS_DIR = BASE_DIR / "teacher_certificates"  # where teacher photos live
    QR_DIR = BASE_DIR / "qr_storage"
    REPORT_DIR = BASE_DIR / "reports"

    # convenience for URL prefix if you ever want to mount images under a route
    STATIC_IMAGE_URL = "/photos"
    STATIC_IMAGE_PATH = DOCUMENT_DIR
