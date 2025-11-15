"""
Safe initialization helper that WILL NOT crash the app on failure.
Logs problems and returns a boolean success flag.
"""

import logging
import traceback
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


def initialize_directories():
    """Create required folders (safe, idempotent)."""
    dirs = [
        Config.BACKUP_DIR,
        Config.DOCUMENT_DIR,
        Config.TEACHER_PHOTOS_DIR,
        Config.TEACHER_CERTS_DIR,
        Config.QR_DIR,
        Config.REPORT_DIR,
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info("[INIT] All required directories verified.")
    return True


def seed_default_admin(app):
    """
    Idempotent admin seeding.
    Returns (True, message) on success, (False, errmsg) on failure.
    """
    try:
        from app import db
        from app.models import User

        with app.app_context():
            db.create_all()

            username = Config.DEFAULT_ADMIN_USER
            email = Config.DEFAULT_ADMIN_EMAIL
            password = Config.DEFAULT_ADMIN_PASS

            existing = User.query.filter_by(username=username).first()
            if not existing:
                admin = User(username=username, email=email, role="admin")
                admin.set_password(password)
                db.session.add(admin)
                db.session.commit()
                msg = "[INIT] Admin user created successfully."
                logger.info(msg)
                return True, msg
            else:
                msg = "[INIT] Admin user already exists."
                logger.info(msg)
                return True, msg

    except Exception:
        errmsg = f"[INIT][ERROR] Seeding admin failed:\n{traceback.format_exc()}"
        logger.error(errmsg)
        return False, errmsg
