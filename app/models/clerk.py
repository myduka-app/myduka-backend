from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from app import db 
from app.models.user_models import Clerk, Admin, Merchant 
from app.utils.validators import validate_email, validate_password
from app.auth.permissions import merchant_required, admin_required, clerk_required 


clerk_bp = Blueprint('clerk_bp', __name__)
api = Api(clerk_bp)

class ClerkRegistrationByAdmin(Resource):
    """
    Allows an Admin to register a new Clerk.
    """
    @jwt_required()
    @admin_required()
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

        current_admin_id = get_jwt_identity()
        admin = Admin.query.get(current_admin_id)
        if not admin:
            return {'message': 'Admin not found'}, 404 

        try:
            new_clerk = Clerk(username=username, email=email, admin_id=admin.id)
            new_clerk.password = password 
            db.session.add(new_clerk)
            db.session.commit()
            return {'message': 'Clerk registered successfully', 'clerk': new_clerk.to_dict()}, 201
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username or email already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error registering clerk: {e}")
            return {'message': 'An internal server error occurred during clerk registration.'}, 500

class ClerkResource(Resource):
    """
    Handles operations on a single Clerk account (get, update, deactivate/delete).
    Clerks can manage their own profile. Admins can manage any clerk's profile.
    Merchants can also manage any clerk's profile.
    """
    @jwt_required()
    def get(self, clerk_id=None):
        current_user_id = get_jwt_identity()
       
        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser
        is_admin = admin is not None

        if clerk_id is None: 
            clerk = Clerk.query.get(current_user_id)
            if not clerk: 
                return {'message': 'Clerk profile not found or access denied'}, 404
            
            return {'clerk': clerk.to_dict()}, 200
        else: 
            if not (is_merchant or is_admin):
                return {'message': 'Admin or Merchant access required to view other clerk profiles'}, 403

            clerk = Clerk.query.get(clerk_id)
            if not clerk:
                return {'message': 'Clerk not found'}, 404
            return {'clerk': clerk.to_dict()}, 200

    @jwt_required()
    def put(self, clerk_id=None):
        current_user_id = get_jwt_identity()
        data = request.get_json()

        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser
        is_admin = admin is not None

        if clerk_id is None: 
            clerk = Clerk.query.get(current_user_id)
            if not clerk:
                return {'message': 'Clerk profile not found'}, 404
            target_clerk = clerk
        else:
            if not (is_merchant or is_admin):
                return {'message': 'Admin or Merchant access required to update other clerk profiles'}, 403
            target_clerk = Clerk.query.get(clerk_id)
            if not target_clerk:
                return {'message': 'Clerk not found'}, 404

        username = data.get('username', target_clerk.username)
        email = data.get('email', target_clerk.email)
        password = data.get('password')
        is_active = data.get('is_active', target_clerk.is_active)

        if username:
            target_clerk.username = username
        if email:
            if not validate_email(email):
                return {'message': 'Invalid email format'}, 400
            target_clerk.email = email
        if password:
            if not validate_password(password):
                return {'message': 'Password does not meet requirements'}, 400
            target_clerk.password = password 

        
        if isinstance(is_active, bool) and (is_merchant or is_admin):
            target_clerk.is_active = is_active
        elif isinstance(is_active, bool) and not (is_merchant or is_admin) and is_active != target_clerk.is_active:
            
            return {'message': 'Clerks cannot change their own active status'}, 403

        try:
            db.session.commit()
            return {'message': 'Clerk updated successfully', 'clerk': target_clerk.to_dict()}, 200
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username or email already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error updating clerk: {e}")
            return {'message': 'An internal server error occurred during update.'}, 500

    @jwt_required()
    def delete(self, clerk_id):
        """
        Deletes a clerk account (only by Admin or Merchant).
        """
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser
        is_admin = admin is not None

        if not (is_merchant or is_admin):
            return {'message': 'Admin or Merchant access required to delete clerk accounts'}, 403

        clerk = Clerk.query.get(clerk_id)
        if not clerk:
            return {'message': 'Clerk not found'}, 404

        try:
            db.session.delete(clerk)
            db.session.commit()
            return {'message': 'Clerk account deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting clerk: {e}")
            return {'message': 'An internal server error occurred during deletion.'}, 500

class ClerkListResource(Resource):
    """
    Allows Admin or Merchant to view all Clerks.
    """
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser
        is_admin = admin is not None

        if not (is_merchant or is_admin):
            return {'message': 'Admin or Merchant access required to view clerks'}, 403

        clerks = Clerk.query.all()
        return {'clerks': [clerk.to_dict() for clerk in clerks]}, 200



api.add_resource(ClerkRegistrationByAdmin, '/register') 
api.add_resource(ClerkListResource, '/') 
api.add_resource(ClerkResource, '/profile', endpoint='clerk_profile') 
api.add_resource(ClerkResource, '/<int:clerk_id>', endpoint='clerk_by_id') 

