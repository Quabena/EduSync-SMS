from flask import Blueprint

bp = Blueprint("learning", __name__, url_prefix="/learning")

from app.learning import routes
