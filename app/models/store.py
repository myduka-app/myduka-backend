

from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from app import db 
from app.models.user_models import Merchant, Admin 
from app.auth.permissions import merchant_required, admin_required 
from datetime import datetime


store_bp = Blueprint('store_bp', __name__)
api = Api(store_bp)

class Store(db.Model):
    """
    Represents a physical store location.
    Managed by a Merchant, and can be assigned an Admin.
    """
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

   
    inventories = db.relationship('Inventory', backref='store', lazy=True)
   

    def __repr__(self):
        return f'<Store {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'is_active': self.is_active,
            'merchant_id': self.merchant_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class StoreListResource(Resource):
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser
        is_admin = admin is not None

        if not (is_merchant or is_admin):
            return {'message': 'Merchant or Admin access required to view stores'}, 403

        stores = Store.query.all()
        return {'stores': [store.to_dict() for store in stores]}, 200

    @jwt_required()
    @merchant_required()
    def post(self):
        data = request.get_json()
        name = data.get('name')
        location = data.get('location')
        current_merchant_id = get_jwt_identity()

        if not all([name, location]):
            return {'message': 'Missing required fields: name, location'}, 400

        try:
            new_store = Store(name=name, location=location, merchant_id=current_merchant_id)
            db.session.add(new_store)
            db.session.commit()
            return {'message': 'Store created successfully', 'store': new_store.to_dict()}, 201
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Store with this name already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error creating store: {e}")
            return {'message': 'An internal server error occurred during store creation.'}, 500

class StoreResource(Resource):
    @jwt_required()
    def get(self, store_id):
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser

        store = Store.query.get(store_id)
        if not store:
            return {'message': 'Store not found'}, 404

        if is_merchant:
            return {'store': store.to_dict()}, 200
        elif admin and admin.store_id == store_id:
            return {'store': store.to_dict()}, 200
        else:
            return {'message': 'Unauthorized to view this store'}, 403

    @jwt_required()
    def put(self, store_id):
        current_user_id = get_jwt_identity()
        merchant = Merchant.query.get(current_user_id)
        admin = Admin.query.get(current_user_id)
        is_merchant = merchant and merchant.is_superuser

        store = Store.query.get(store_id)
        if not store:
            return {'message': 'Store not found'}, 404

        if not (is_merchant or (admin and admin.store_id == store_id)):
            return {'message': 'Unauthorized to update this store'}, 403

        data = request.get_json()
        name = data.get('name', store.name)
        location = data.get('location', store.location)
        is_active = data.get('is_active', store.is_active)

        if name:
            store.name = name
        if location:
            store.location = location
        if isinstance(is_active, bool) and is_merchant:
            store.is_active = is_active
        elif isinstance(is_active, bool) and not is_merchant and is_active != store.is_active:
            return {'message': 'Only Merchant can change store active status'}, 403

        try:
            db.session.commit()
            return {'message': 'Store updated successfully', 'store': store.to_dict()}, 200
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Store with this name already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error updating store: {e}")
            return {'message': 'An internal server error occurred during store update.'}, 500

    @jwt_required()
    @merchant_required()
    def delete(self, store_id):
        store = Store.query.get(store_id)
        if not store:
            return {'message': 'Store not found'}, 404

        try:
            db.session.delete(store)
            db.session.commit()
            return {'message': 'Store deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting store: {e}")
            return {'message': 'An internal server error occurred during store deletion.'}, 500


api.add_resource(StoreListResource, '/')
api.add_resource(StoreResource, '/<int:store_id>')
