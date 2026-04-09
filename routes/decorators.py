"""Shared route decorators."""
from functools import wraps
from flask import jsonify
from flask_login import current_user


def api_auth(f):
    """Require authenticated user for API endpoints."""
    @wraps(f)
    def wrapped(*a, **kw):
        if not current_user.is_authenticated:
            return jsonify({"error": "Login required"}), 401
        return f(*a, **kw)
    return wrapped
