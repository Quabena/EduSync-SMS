from flask import Blueprint

bp = Blueprint("exams_grading", __name__, url_prefix="/exams_grading")

from app.exams_grading import routes
