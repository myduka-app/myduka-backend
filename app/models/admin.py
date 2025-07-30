from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from app import db 
from app.models.user_models import Admin, Merchant 
from app.models.store import Store 
from app.utils.validators import validate_email, validate_password
from app.auth.permissions import merchant_required, admin_required


admin_bp = Blueprint('admin_bp', __name__)
api = Api(admin_bp)

class AdminRegistrationByMerchant(Resource):
    """
    Allows a Merchant to register a new Admin.
    This is a direct registration for now. Later, this could be an invitation system.
    """
    @jwt_required()
    @merchant_required()
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

        current_merchant_id = get_jwt_identity()
        merchant = Merchant.query.get(current_merchant_id)
        if not merchant:
            return {'message': 'Merchant not found'}, 404 

        try:
            new_admin = Admin(username=username, email=email, merchant_id=merchant.id)
            new_admin.password = password 
            db.session.add(new_admin)
            db.session.commit()
            return {'message': 'Admin registered successfully', 'admin': new_admin.to_dict()}, 201
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username or email already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error registering admin: {e}")
            return {'message': 'An internal server error occurred during admin registration.'}, 500

class AdminResource(Resource):
    """
    Handles operations on a single Admin account (get, update, deactivate/delete).
    Admins can manage their own profile. Merchants can manage any admin's profile.
    """
    @jwt_required()
    def get(self, admin_id=None):
        current_user_id = get_jwt_identity()
        
        if admin_id is None: 
            admin = Admin.query.get(current_user_id)
            if not admin: 
                return {'message': 'Admin profile not found or access denied'}, 404
            
            return {'admin': admin.to_dict()}, 200
        else: 
            merchant = Merchant.query.get(current_user_id)
            if not merchant or not merchant.is_superuser:
                return {'message': 'Merchant access required to view other admin profiles'}, 403

            admin = Admin.query.get(admin_id)
            if not admin:
                return {'message': 'Admin not found'}, 404
            return {'admin': admin.to_dict()}, 200

    @jwt_required()
    def put(self, admin_id=None):
        current_user_id = get_jwt_identity()
        data = request.get_json()

        merchant = Merchant.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser

        if admin_id is None: 
            admin = Admin.query.get(current_user_id)
            if not admin:
                return {'message': 'Admin profile not found'}, 404
            target_admin = admin
        else: 
            if not is_merchant:
                return {'message': 'Merchant access required to update other admin profiles'}, 403
            target_admin = Admin.query.get(admin_id)
            if not target_admin:
                return {'message': 'Admin not found'}, 404

        username = data.get('username', target_admin.username)
        email = data.get('email', target_admin.email)
        password = data.get('password')
        is_active = data.get('is_active', target_admin.is_active)
        store_id = data.get('store_id') 

        if username:
            target_admin.username = username
        if email:
            if not validate_email(email):
                return {'message': 'Invalid email format'}, 400
            target_admin.email = email
        if password:
            if not validate_password(password):
                return {'message': 'Password does not meet requirements'}, 400
            target_admin.password = password 
        if isinstance(is_active, bool) and is_merchant: 
            target_admin.is_active = is_active
        elif isinstance(is_active, bool) and not is_merchant and is_active != target_admin.is_active:
            
            return {'message': 'Admins cannot change their own active status'}, 403

        
        if store_id is not None: 
            if not is_merchant:
                return {'message': 'Only Merchant can assign/unassign stores to admins'}, 403

            if store_id == 0: 
                target_admin.store_id = None
            else:
                store = Store.query.get(store_id)
                if not store:
                    return {'message': f'Store with ID {store_id} not found'}, 404
                if store.merchant_id != current_user_id: 
                    return {'message': 'Store does not belong to your merchant account'}, 403
                target_admin.store_id = store_id
        

        try:
            db.session.commit()
            return {'message': 'Admin updated successfully', 'admin': target_admin.to_dict()}, 200
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username or email already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error updating admin: {e}")
            return {'message': 'An internal server error occurred during update.'}, 500

    @jwt_required()
    @merchant_required()
    def delete(self, admin_id):
        """
        Deletes an admin account (only by Merchant).
        """
        admin = Admin.query.get(admin_id)
        if not admin:
            return {'message': 'Admin not found'}, 404

        try:
            db.session.delete(admin)
            db.session.commit()
            return {'message': 'Admin account deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting admin: {e}")
            return {'message': 'An internal server error occurred during deletion.'}, 500

class AdminListResource(Resource):
    """
    Allows Merchant to view all Admins.
    """
    @jwt_required()
    @merchant_required()
    def get(self):
        admins = Admin.query.all()
        return {'admins': [admin.to_dict() for admin in admins]}, 200



api.add_resource(AdminRegistrationByMerchant, '/register') 
api.add_resource(AdminListResource, '/') 
api.add_resource(AdminResource, '/profile', endpoint='admin_profile') 
api.add_resource(AdminResource, '/<int:admin_id>', endpoint='admin_by_id') 

