from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from app import db 
from app.models.user_models import Merchant 
from app.utils.validators import validate_email, validate_password
from app.auth.permissions import merchant_required 


merchant_bp = Blueprint('merchant_bp', __name__)
api = Api(merchant_bp)



class MerchantRegistration(Resource):
    """
    Handles initial superuser (merchant) registration.
    This route might be protected differently or have a one-time setup mechanism.
    For now, it's a basic registration.
    """
    def post(self):
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([username, email, password]):
            return {'message': 'Missing required fields: username, email, password'}, 400
        if not validate_email(email):
            return {'message': 'Invalid email format'}, 400
        if not validate_password(password):
            return {'message': 'Password does not meet requirements'}, 400

        
        if Merchant.query.first():
            return {'message': 'Superuser (Merchant) already exists. Registration not allowed.'}, 403

        try:
            new_merchant = Merchant(username=username, email=email)
            new_merchant.password = password 
            db.session.add(new_merchant)
            db.session.commit()
            return {'message': 'Superuser (Merchant) registered successfully', 'merchant': new_merchant.to_dict()}, 201
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username or email already exists'}, 409
        except Exception as e:
            db.session.rollback()
            
            print(f"Error during merchant registration: {e}")
            return {'message': 'An internal server error occurred during registration.'}, 500

class MerchantResource(Resource):
    """
    Handles operations on a single merchant (superuser) account.
    Requires merchant authentication.
    """
    @jwt_required()
    @merchant_required() 
    def get(self):
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        if not merchant:
            return {'message': 'Merchant not found'}, 404
        return {'merchant': merchant.to_dict()}, 200

    @jwt_required()
    @merchant_required() 
    def put(self):
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        if not merchant:
            return {'message': 'Merchant not found'}, 404

        data = request.get_json()
        username = data.get('username', merchant.username)
        email = data.get('email', merchant.email)
        password = data.get('password')
        is_active = data.get('is_active', merchant.is_active)

        if username:
            merchant.username = username
        if email:
            if not validate_email(email):
                return {'message': 'Invalid email format'}, 400
            merchant.email = email
        if password:
            if not validate_password(password):
                return {'message': 'Password does not meet requirements'}, 400
            merchant.password = password 
        if isinstance(is_active, bool):
            merchant.is_active = is_active

        try:
            db.session.commit()
            return {'message': 'Merchant updated successfully', 'merchant': merchant.to_dict()}, 200
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username or email already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error during merchant update: {e}")
            return {'message': 'An internal server error occurred during update.'}, 500

    @jwt_required()
    @merchant_required() 
    def delete(self):
        """
        Deletes the merchant account. This should be handled with extreme caution
        as it's the superuser account.
        """
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        if not merchant:
            return {'message': 'Merchant not found'}, 404

        try:
            db.session.delete(merchant)
            db.session.commit()
            return {'message': 'Merchant account deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error during merchant deletion: {e}")
            return {'message': 'An internal server error occurred during deletion.'}, 500


api.add_resource(MerchantRegistration, '/register')
api.add_resource(MerchantResource, '/profile')

