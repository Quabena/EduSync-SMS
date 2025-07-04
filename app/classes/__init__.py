from flask import Blueprint

bp = Blueprint("classes", __name__, url_prefix="/classes")

from app.classes import routes
