from flask import Blueprint

bp = Blueprint("subjects", __name__, url_prefix="/subjects")

from app.subjects import routes
