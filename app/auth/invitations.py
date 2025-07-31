

from flask import Blueprint, request, jsonify, url_for, current_app
from flask_restful import Api, Resource
from flask_mail import Message
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, decode_token
from datetime import timedelta
from sqlalchemy.exc import IntegrityError

from app import mail, db 
from app.models.user_models import Merchant, Admin 
from app.utils.validators import validate_email, validate_password 
from app.auth.permissions import merchant_required


invitations_bp = Blueprint('invitations_bp', __name__)
api = Api(invitations_bp)

class AdminInvitation(Resource):
    """
    Allows a Merchant to send an invitation email to a new Admin.
    The invitation contains a tokenized link for registration.
    """
    @jwt_required()
    @merchant_required()
    def post(self):
        data = request.get_json()
        email = data.get('email')
        invited_by_id = get_jwt_identity() 

        if not email:
            return {'message': 'Email is required for invitation'}, 400
        if not validate_email(email):
            return {'message': 'Invalid email format'}, 400

        
        if Admin.query.filter_by(email=email).first():
            return {'message': 'An admin with this email already exists'}, 409

      
        invitation_token = create_access_token(
            identity={'email': email, 'invited_by': invited_by_id},
            expires_delta=timedelta(hours=current_app.config['INVITATION_TOKEN_EXPIRY']),
            additional_claims={'purpose': 'admin_invitation'}
        )

        # Construct the invitation link for the frontend
        invitation_link = f"http://localhost:5000/auth/register-admin-with-token?token={invitation_token}"

        try:
            msg = Message(
                subject="MyDuka Admin Invitation",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[email]
            )
            msg.body = f"""
            You have been invited to register as an Admin for MyDuka by a Merchant.

            Please click on the link below to complete your registration:
            {invitation_link}

            This invitation link is valid for {current_app.config['INVITATION_TOKEN_EXPIRY']} hours.
            If you did not request this, please ignore this email.
            """
            mail.send(msg)
            return {'message': f'Invitation sent to {email}', 'invitation_link_for_testing': invitation_link}, 200
        except Exception as e:
            print(f"Error sending invitation email: {e}")
            return {'message': 'Failed to send invitation email', 'error': str(e)}, 500

class AdminRegistrationWithToken(Resource):
    """
    Allows an invited user to register as an Admin using a tokenized link.
    """
    def post(self):
        token = request.args.get('token')
        if not token:
            return {'message': 'Invitation token is missing'}, 400

        try:
            #
            decoded_token = decode_token(token)
        except Exception as e:
            return {'message': f'Invalid or expired token: {str(e)}'}, 401

        if decoded_token.get('purpose') != 'admin_invitation':
            return {'message': 'Invalid token purpose for admin registration'}, 403

        
        invited_email = decoded_token['sub']['email']
        invited_by_id = decoded_token['sub']['invited_by']

        
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not all([username, password]):
            return {'message': 'Missing required fields: username, password'}, 400
        if not validate_password(password): 
            return {'message': 'Password does not meet requirements'}, 400

       
        if Admin.query.filter_by(email=invited_email).first():
            return {'message': 'An admin with this email already exists'}, 409

        try:
            new_admin = Admin(username=username, email=invited_email, merchant_id=invited_by_id)
            new_admin.password = password
            db.session.add(new_admin)
            db.session.commit()
            return {'message': 'Admin registration successful', 'admin': new_admin.to_dict()}, 201
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Username already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error during token-based admin registration: {e}")
            return {'message': 'An internal server error occurred during registration.'}, 500


api.add_resource(AdminInvitation, '/invite-admin')
api.add_resource(AdminRegistrationWithToken, '/register-admin-with-token')
