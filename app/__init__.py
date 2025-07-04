from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initializing extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # type: ignore

    # Creating storage directories
    from app.utils.setup import create_storage_dirs

    create_storage_dirs(app)

    # Registering blueprints
    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp

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

    return app
