

from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.models.user_models import Merchant, Admin, Clerk 

def merchant_required():
    """
    Decorator to ensure the current authenticated user is a Merchant (superuser).
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            current_user_id = get_jwt_identity()
            merchant = Merchant.query.get(current_user_id)

            if not merchant or not merchant.is_superuser:
                return jsonify({'message': 'Merchant (Superuser) access required'}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def admin_required():
    """
    Decorator to ensure the current authenticated user is an Admin.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            current_user_id = get_jwt_identity()
            admin = Admin.query.get(current_user_id)

            if not admin: 
                return jsonify({'message': 'Admin access required'}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def clerk_required():
    """
    Decorator to ensure the current authenticated user is a Clerk.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            current_user_id = get_jwt_identity()
            clerk = Clerk.query.get(current_user_id)

            if not clerk:
                return jsonify({'message': 'Clerk access required'}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper