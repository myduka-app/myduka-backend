

from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, get_jwt_identity,
    get_jwt, JWTManager
)
from datetime import timedelta

from app import db, jwt 
from app.models.user_models import Merchant, Admin, Clerk 
from app.utils.validators import validate_email 


auth_bp = Blueprint('auth_bp', __name__)
api = Api(auth_bp)


blacklist = set()

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    """
    Callback function to check if a JWT has been revoked.
    """
    jti = jwt_payload["jti"]
    return jti in blacklist



class UserLogin(Resource):
    """
    Handles user login for Merchant, Admin, and Clerk.
    """
    def post(self):
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not all([email, password]):
            return {'message': 'Missing email or password'}, 400
        if not validate_email(email):
            return {'message': 'Invalid email format'}, 400

        user = None
        user_type = None

        
        merchant = Merchant.query.filter_by(email=email).first()
        if merchant:
            user = merchant
            user_type = 'merchant'
        else:
            admin = Admin.query.filter_by(email=email).first()
            if admin:
                user = admin
                user_type = 'admin'
            else:
                clerk = Clerk.query.filter_by(email=email).first()
                if clerk:
                    user = clerk
                    user_type = 'clerk'

        if not user or not user.check_password(password):
            return {'message': 'Invalid credentials'}, 401
        
        if not user.is_active:
            return {'message': 'Account is inactive. Please contact support.'}, 403

       
        access_token = create_access_token(identity=user.id, additional_claims={"user_type": user_type})
        refresh_token = create_refresh_token(identity=user.id, additional_claims={"user_type": user_type})

        return {
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user_type': user_type,
            'user_id': user.id
        }, 200

class UserLogout(Resource):
    """
    Handles user logout by revoking the access token.
    """
    @jwt_required()
    def post(self):
        jti = get_jwt()["jti"] 
        blacklist.add(jti) 
        return {'message': 'Successfully logged out'}, 200

class TokenRefresh(Resource):
    """
    Allows users to get a new access token using their refresh token.
    """
    @jwt_required(refresh=True) 
    def post(self):
        current_user_id = get_jwt_identity()
        user_claims = get_jwt()
        user_type = user_claims.get("user_type")

        
        new_access_token = create_access_token(identity=current_user_id, additional_claims={"user_type": user_type})
        return {'access_token': new_access_token}, 200


api.add_resource(UserLogin, '/login')
api.add_resource(UserLogout, '/logout')
api.add_resource(TokenRefresh, '/refresh')
