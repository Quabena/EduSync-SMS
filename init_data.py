"""
Safe initialization helper that WILL NOT crash the app on failure.
Logs problems and returns a boolean success flag.
"""

import traceback
from pathlib import Path
from config import Config


def initialize_directories():
    """Create required folders (safe, does not require app instance)."""
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
    print("[INIT] All required directories verified.")
    return True


def seed_default_admin(
    app, username="Vanny", email="vanny@namongsdajhs.edu", password="pass777van"
):
    """
    Idempotent seeding. Returns (True, message) on success, (False, errmsg) on failure.
    Any exceptions are caught and returned, not raised.
    """
    try:
        # Lazy imports to avoid circular import at module load
        from app import db
        from app.models import User

        with app.app_context():
            # Ensure tables exist
            db.create_all()

            existing = User.query.filter_by(username=username).first()
            if not existing:
                admin = User(username=username, email=email, role="admin")
                admin.set_password(password)
                db.session.add(admin)
                db.session.commit()
                msg = "[INIT] Admin user created successfully."
                print(msg)
                return True, msg
            else:
                msg = "[INIT] Admin user already exists."
                print(msg)
                return True, msg

    except Exception as exc:
        # Return the full traceback string to the caller for logging
        tb = traceback.format_exc()
        errmsg = f"[INIT][ERROR] Seeding admin failed: {exc}\n{tb}"
        print(errmsg)
        return False, errmsg


if __name__ == "__main__":
    # CLI invocation: will create an app and attempt seeding.
    from app import create_app

    app = create_app()
    initialize_directories()
    ok, message = seed_default_admin(app)
    if not ok:
        print("Seeding finished with error (see above).")
