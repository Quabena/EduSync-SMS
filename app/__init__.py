import os
from pathlib import Path
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_moment import Moment
from dotenv import load_dotenv
from config import Config

# loading .env
load_dotenv()

# --- EXTENSION INSTANCES ---
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
moment = Moment()


def basename_filter(path):
    return os.path.basename(path)


def create_app(config_class=Config):
    """Application factory"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Convert all storage config values to Path() objects
    STORAGE_KEYS = (
        "BACKUP_DIR",
        "DOCUMENT_DIR",
        "TEACHER_PHOTOS_DIR",
        "TEACHER_CERTS_DIR",
        "QR_DIR",
        "REPORT_DIR",
    )

    for key in STORAGE_KEYS:
        val = app.config.get(key)

        if isinstance(val, Path):
            # already a Path – nothing to do
            app.config[key] = val
        elif isinstance(val, str):
            # convert non-empty string → Path
            app.config[key] = Path(val) if val.strip() else Path()
        else:
            # fallback: force Path
            app.config[key] = Path(str(val))

    # Initialize Flask extensions
    moment.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # type: ignore
    csrf.init_app(app)

    # Template filters and helpers
    app.add_template_filter(basename_filter, name="basename")

    try:
        from app.utils.grading import get_grade

        app.add_template_filter(get_grade, name="get_grade")
        app.add_template_global(get_grade, name="get_grade")
    except Exception as e:
        raise RuntimeError(f"Error loading grading utility: {e}")

    # Ensure storage directories exist
    from app.utils.setup import create_storage_dirs

    create_storage_dirs(app)

    # Register Blueprints (imported here to avoid circular imports)
    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp

    app.register_blueprint(main_bp)

    from app.students import bp as students_bp

    app.register_blueprint(students_bp)

    from app.subjects import bp as subjects_bp

    app.register_blueprint(subjects_bp)

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

    # Create database tables + run seeding
    with app.app_context():
        from . import models

        db.create_all()

        # Lazy-load seeding functions
        try:
            from init_data import initialize_directories, seed_default_admin

            initialize_directories()  # Safe; creates folders if missing

            ok, message = seed_default_admin(app)
            if not ok:
                app.logger.error("Seeder reported error: %s", message)
            else:
                app.logger.info("Seeder success: %s", message)

        except Exception:
            app.logger.exception("Unexpected error while running init_data seeder")

    return app
