from flask import Blueprint

bp = Blueprint("students", __name__, url_prefix="/students")

from app.students import routes
