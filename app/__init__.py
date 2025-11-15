# app/__init__.py
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment
from config import Config
import os
import logging
from logging.handlers import RotatingFileHandler

# NOTE: removed `from init_data import initialize_directories, seed_default_admin`
# to avoid circular import at module import time.

# Extension instances (module-level so other modules can import them)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def basename_filter(path):
    return os.path.basename(path)


def create_app(config_class=Config):
    """App factory"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # log_dir = Path(app.config.get("BASE_DIR", Path.home() / "EduSyncLogs")) / "logs"
    # log_dir.mkdir(parents=True, exist_ok=True)
    # log_file = log_dir / "backend.log"

    # handler = RotatingFileHandler(
    #     str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3
    # )
    # handler.setLevel(logging.INFO)
    # formatter = logging.Formatter(
    #     "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    # )
    # handler.setFormatter(formatter)
    # app.logger.addHandler(handler)

    # # Optional: also set werkzeug logger to write into same file
    # import logging as _logging

    # werkzeug_logger = _logging.getLogger("werkzeug")
    # werkzeug_logger.addHandler(handler)

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
            app.config[key] = Path(str(val))

    # Initialize extensions (do this before importing code that may rely on them)
    Moment(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # type: ignore

    # Initialize CSRF early so blueprints can rely on it
    csrf.init_app(app)

    # Import get_grade here to avoid circular imports.
    # Make sure app.utils.grading does NOT import 'app' (should be a pure helper).
    try:
        from app.utils.grading import get_grade
    except Exception:
        # If anything goes wrong importing the grading helper, surface a clearer error.
        raise

    # Register get_grade both as a filter (pipe-style) and as a template global (callable)
    app.add_template_filter(get_grade, name="get_grade")
    app.add_template_global(get_grade, name="get_grade")

    # Register other small template filters/globals
    app.add_template_filter(basename_filter, name="basename")

    # Create required storage directories (helper expects the app)
    from app.utils.setup import create_storage_dirs

    create_storage_dirs(app)

    # Register blueprints (import them here to avoid circular imports)
    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp

    app.register_blueprint(main_bp)

    from app.students import bp as students_bp

    app.register_blueprint(students_bp)

    from app.subjects import bp as subject_bp

    app.register_blueprint(subject_bp)

    from app.classes import bp as classes_bp

    app.register_blueprint(classes_bp)

    from app.teachers import bp as teachers_bp

    app.register_blueprint(teachers_bp)

    from app.teacher_attendance import bp as teacher_attendance_bp

    app.register_blueprint(teacher_attendance_bp)

    from app.attendance import bp as attendance_bp

    app.register_blueprint(attendance_bp)

    from app.mood import bp as mood_bp

    app.register_blueprint(mood_bp)

    from app.exams_grading import bp as exams_grading_bp

    app.register_blueprint(exams_grading_bp)

    from app.student_promotion import bp as student_promotion_bp

    app.register_blueprint(student_promotion_bp)

    from app.graduation import bp as alumni_bp

    app.register_blueprint(alumni_bp)

    from app.search.routes import bp as search_bp

    app.register_blueprint(search_bp)

    # Import models and create tables while app context is active,
    # then run the seeder here (imported lazily to avoid cycles).
    with app.app_context():
        from . import models  # your models so db.create_all knows tables

        db.create_all()

        # Lazy import and run seeder safely
        try:
            from init_data import initialize_directories, seed_default_admin

            # ensure directories exist (safe)
            initialize_directories()

            # seed admin, but don't allow seeder to raise
            ok, message = seed_default_admin(app)
            if not ok:
                # Log the detailed error message (it's the traceback string)
                app.logger.error("Seeder reported error: %s", message)
            else:
                app.logger.info("Seeder success: %s", message)

        except Exception:
            # This outer try/catch is extra safe: it logs any unexpected errors
            app.logger.exception("Unexpected error while running init_data seeder")

    return app
