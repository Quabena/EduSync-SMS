import os
import shutil
import csv
import sqlite3
import zipfile
import json
from datetime import datetime
from pathlib import Path
from flask import current_app
from app.models import db


def detect_usb_drives():
    """Detect available USB drives on the system"""
    drives = []

    # Platform-specific detection
    if os.name == "nt":  # For Windows
        import win32api
        import win32file

        drives = win32api.GetLogicalDriveStrings()
        drives = drives.split("\000")[:-1]
        drives = [
            d for d in drives if win32file.GetDriveType(d) == win32file.DRIVE_REMOVABLE
        ]
    else:  # Linux/Mac
        drives = [os.path.join("/media", d) for d in os.listdir("/media")]
        drives = [d for d in drives if os.path.ismount(d)]

    return drives


def export_to_usb(drive_path, export_type="all"):
    """Export data to USB drive"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = Path(drive_path) / f"sms_export_{timestamp}"
        export_dir.mkdir(parents=True, exist_ok=True)
        if not Path(drive_path).exists():
            raise ValueError(
                f"Drive path {drive_path} does not exist or is not accessible"
            )
        if not os.access(drive_path, os.W_OK):
            raise PermissionError(f"Cannot write to drive {drive_path}")

        # Export database
        db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not db_uri.startswith("sqlite:///"):
            raise ValueError("Usupported database URI format")
        db_path = Path(db_uri.replace("sqlite:///", ""))
        shutil.copy(db_path, export_dir / "namongsdajhs.db")

        # Export documents
        shutil.copytree(
            current_app.config["DOCUMENT_DIR"],
            export_dir / "documents",
            dirs_exist_ok=True,
        )

        # Export reports
        shutil.copytree(
            current_app.config["REPORT_DIR"], export_dir / "reports", dirs_exist_ok=True
        )

        # Create manifest
        manifest = {
            "export_type": export_type,
            "timestamp": timestamp,
            "file_count": sum(len(files) for _, _, files in os.walk(export_dir)),
        }

        with open(export_dir / "manifest.json", "w") as f:
            json.dump(manifest, f)

        return True, f"Export successful to {export_dir}"
    except Exception as e:
        return False, str(e)


def import_from_usb(drive_path):
    """Import data from USB drive"""

    # Import database - I declared this outside the try block to avoid unbound errors
    db_path = Path(
        current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    )
    backup_path = db_path.with_suffix(".bak")

    try:
        # Find latest export directory
        export_dirs = [
            d
            for d in Path(drive_path).iterdir()
            if d.is_dir() and d.name.startswith("sms_export_")
        ]
        if not export_dirs:
            return False, "No valid export directories found"

        latest_export = max(export_dirs, key=os.path.getmtime)

        # Create backup
        shutil.copy(db_path, backup_path)

        # Replace database
        shutil.copy(latest_export / "school.db", db_path)

        # Import documents
        shutil.copytree(
            latest_export / "documents",
            current_app.config["DOCUMENT_DIR"],
            dirs_exist_ok=True,
        )

        # Import reports
        shutil.copytree(
            latest_export / "reports",
            current_app.config["REPORT_DIR"],
            dirs_exist_ok=True,
        )

        return True, "Import successful"
    except Exception as e:
        # Restore backup if import failed
        if backup_path.exists():
            shutil.copy(backup_path, db_path)
        return False, str(e)
