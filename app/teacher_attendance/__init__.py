from flask import Blueprint

bp = Blueprint("teacher_attendance", __name__, url_prefix="/teacher_attendance")

from app.teacher_attendance import routes
