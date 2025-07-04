import os
import shutil
from datetime import datetime
from pathlib import Path
from flask import current_app
from app.models import db


def backup_database():
    """Database backup"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_path = Path(
            current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
        )
        backup_path = current_app.config["BACKUP_DIR"] / f"namongsdajhs_{timestamp}.db"

        shutil.copy(db_path, backup_path)

        # Keeping only the last 7 backups
        backups = sorted(
            current_app.config["BACKUP_DIR"].glob("namongsdajhs_*.db"), reverse=True
        )
        for old_backup in backups[7:]:
            old_backup.unlink()

        return True, f"Backup created: {backup_path.name}"
    except Exception as e:
        return False, str(e)


def restore_database(backup_name):
    """Restoring database from backup"""
    try:
        db_path = Path(
            current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
        )
        backup_path = current_app.config["BACKUP_DIR"] / backup_name

        if not backup_path.exists():
            return False, "Backup file not found!"

        # Creating temporary backup
        temp_backup = db_path.with_suffix(".bak")
        shutil.copy(db_path, temp_backup)

        try:
            # Restoring from selected backup
            shutil.copy(backup_path, db_path)
            return True, "Database restored successfully!"
        except Exception as e:
            return False, f"Restore failed!: {str(e)}"
        finally:
            if temp_backup.exists():
                temp_backup.unlink()

    except Exception as e:
        return False, str(e)
