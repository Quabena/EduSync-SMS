from flask import Blueprint

bp = Blueprint("student_promotion", __name__, url_prefix="/student-promotion")

from app.student_promotion import routes
