from flask import Blueprint


bp = Blueprint("grading", __name__, url_prefix="/grading")

from app.grading import routes
