from flask import Blueprint

bp = Blueprint("graduation", __name__, url_prefix="/graduation")

from app.graduation import routes
