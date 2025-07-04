from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to access this page", "warning")
                return redirect(url_for("auth.login"))

            if current_user.role not in roles:
                flash("You do not have permission to access this page", "danger")
                return redirect(url_for("main.index"))
            return f(*args, **kwargs)

        return decorated_function

    return decorator
