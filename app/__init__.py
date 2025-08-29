from flask import Flask
from flask_wtf.csrf import CSRFProtect
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def basename_filter(path):
    return os.path.basename(path)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Normalize storage config values -> ensure they are Path objects
    storage_keys = (
        "BACKUP_DIR",
        "DOCUMENT_DIR",
        "TEACHER_PHOTOS_DIR",
        "QR_DIR",
        "REPORT_DIR",
    )
    for key in storage_keys:
        val = app.config.get(key)
        if isinstance(val, Path):
            app.config[key] = val
        elif isinstance(val, str):
            app.config[key] = Path(val)
        else:
            # Try to coerce anything else
            app.config[key] = Path(str(val))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # type: ignore

    # Create the directories (using the util that expects the app)
    from app.utils.setup import create_storage_dirs

    create_storage_dirs(app)

    # Register blueprints
    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp

    app.add_template_filter(basename_filter, name="basename")

    app.register_blueprint(main_bp)

    from app.students import bp as students_bp

    app.register_blueprint(students_bp)

    from app.classes import bp as classes_bp

    app.register_blueprint(classes_bp)

    from app.teachers import bp as teachers_bp

    app.register_blueprint(teachers_bp)

    from app.attendance import bp as attendance_bp

    app.register_blueprint(attendance_bp)

    from app.mood import bp as mood_bp

    app.register_blueprint(mood_bp)

    from app.exams_grading import bp as exams_grading_bp

    app.register_blueprint(exams_grading_bp)

    csrf.init_app(app)

    return app
