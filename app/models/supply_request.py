

from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user_models import Merchant, Admin, Clerk
from app.models.products import Product
from app.models.store import Store
from app.auth.permissions import merchant_required, admin_required, clerk_required
from datetime import datetime


supply_request_bp = Blueprint('supply_request_bp', __name__)
api = Api(supply_request_bp)

class SupplyRequest(db.Model):
    """
    Represents a request for more product supply, made by a Clerk to an Admin.
    """
    __tablename__ = 'supply_requests'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    requested_by_clerk_id = db.Column(db.Integer, db.ForeignKey('clerks.id', ondelete='SET NULL'), nullable=True)
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='SET NULL'), nullable=True)

    quantity_requested = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending', nullable=False) 
    notes = db.Column(db.Text, nullable=True)

    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    response_date = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SupplyRequest {self.id} for Product {self.product_id} in Store {self.store_id} - Status: {self.status}>'

    def to_dict(self):
        product = Product.query.get(self.product_id)
        store = Store.query.get(self.store_id)
        clerk = Clerk.query.get(self.requested_by_clerk_id)
        admin = Admin.query.get(self.approved_by_admin_id)

        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': product.name if product else None,
            'store_id': self.store_id,
            'store_name': store.name if store else None,
            'requested_by_clerk_id': self.requested_by_clerk_id,
            'requested_by_clerk_username': clerk.username if clerk else None,
            'approved_by_admin_id': self.approved_by_admin_id,
            'approved_by_admin_username': admin.username if admin else None,
            'quantity_requested': self.quantity_requested,
            'status': self.status,
            'notes': self.notes,
            'request_date': self.request_date.isoformat() if self.request_date else None,
            'response_date': self.response_date.isoformat() if self.response_date else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }



class SupplyRequestListResource(Resource):
    """
    Handles listing all supply requests and creating new requests.
    Clerks can create requests. Merchant, Admin, Clerk can view requests.
    """
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin', 'clerk']:
            return {'message': 'Authentication required to view supply requests'}, 403

        query = SupplyRequest.query

        if user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin:
                return {'message': 'Admin not found'}, 404
            if admin.store_id: 
                query = query.filter_by(store_id=admin.store_id)
            else:
                return {'message': 'Admin not assigned to a store. Cannot view supply requests.'}, 403
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk:
                return {'message': 'Clerk not found'}, 404
            
            query = query.filter_by(requested_by_clerk_id=current_user_id)
        

        supply_requests = query.all()
        return {'supply_requests': [req.to_dict() for req in supply_requests]}, 200

    @jwt_required()
    @clerk_required() 
    def post(self):
        current_clerk_id = get_jwt_identity()
        clerk = Clerk.query.get(current_clerk_id)
        if not clerk:
            return {'message': 'Clerk not found'}, 404 

        data = request.get_json()
        product_id = data.get('product_id')
        quantity_requested = data.get('quantity_requested')
        notes = data.get('notes')

        if not all([product_id, quantity_requested is not None]):
            return {'message': 'Missing required fields: product_id, quantity_requested'}, 400

        
        try:
            product_id = int(product_id)
            quantity_requested = int(quantity_requested)
            if quantity_requested <= 0:
                return {'message': 'Quantity requested must be positive'}, 400
        except ValueError:
            return {'message': 'product_id and quantity_requested must be valid numbers'}, 400

        
        product = Product.query.get(product_id)
        if not product:
            return {'message': f'Product with ID {product_id} not found'}, 404

        
        if not clerk.store_id:
            return {'message': 'Clerk must be assigned to a store to make a supply request'}, 403

        try:
            new_request = SupplyRequest(
                product_id=product_id,
                store_id=clerk.store_id, 
                requested_by_clerk_id=current_clerk_id,
                quantity_requested=quantity_requested,
                notes=notes,
                status='Pending' 
            )
            db.session.add(new_request)
            db.session.commit()
            return {'message': 'Supply request created successfully', 'request': new_request.to_dict()}, 201
        except Exception as e:
            db.session.rollback()
            print(f"Error creating supply request: {e}")
            return {'message': 'An internal server error occurred during request creation.'}, 500

class SupplyRequestResource(Resource):
    """
    Handles operations on a single supply request (get, update status, delete).
    Admins can approve/decline. Merchant can delete.
    """
    @jwt_required()
    def get(self, request_id):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        req = SupplyRequest.query.get(request_id)
        if not req:
            return {'message': 'Supply request not found'}, 404

        
        if user_type == 'merchant':
            pass 
        elif user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin or (admin.store_id and admin.store_id != req.store_id):
                return {'message': 'Unauthorized to view this supply request'}, 403
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk or clerk.id != req.requested_by_clerk_id:
                return {'message': 'Unauthorized to view this supply request'}, 403
        else:
            return {'message': 'Authentication required to view supply request'}, 403

        return {'supply_request': req.to_dict()}, 200

    @jwt_required()
    @admin_required() 
    def put(self, request_id):
        current_admin_id = get_jwt_identity()
        admin = Admin.query.get(current_admin_id)
        if not admin:
            return {'message': 'Admin not found'}, 404 

        req = SupplyRequest.query.get(request_id)
        if not req:
            return {'message': 'Supply request not found'}, 404

        
        if admin.store_id and admin.store_id != req.store_id:
            return {'message': 'Admin is not assigned to this store to approve requests'}, 403

        data = request.get_json()
        notes = data.get('notes', req.notes) 

        if not status:
            return {'message': 'Status is required to update supply request'}, 400

        valid_statuses = ['Approved', 'Declined', 'Fulfilled']
        if status not in valid_statuses:
            return {'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, 400

        
        if req.status in ['Fulfilled', 'Declined'] and status != req.status:
            return {'message': 'Cannot change status of a fulfilled or declined request'}, 400

        req.status = status
        req.notes = notes
        req.approved_by_admin_id = current_admin_id
        req.response_date = datetime.utcnow()

        try:
            db.session.commit()
            return {'message': 'Supply request updated successfully', 'request': req.to_dict()}, 200
        except Exception as e:
            db.session.rollback()
            print(f"Error updating supply request: {e}")
            return {'message': 'An internal server error occurred during request update.'}, 500

    @jwt_required()
    @merchant_required() 
    def delete(self, request_id):
        req = SupplyRequest.query.get(request_id)
        if not req:
            return {'message': 'Supply request not found'}, 404

        try:
            db.session.delete(req)
            db.session.commit()
            return {'message': 'Supply request deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting supply request: {e}")
            return {'message': 'An internal server error occurred during request deletion.'}, 500


api.add_resource(SupplyRequestListResource, '/')
api.add_resource(SupplyRequestResource, '/<int:request_id>')