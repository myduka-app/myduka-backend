

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


inventory_bp = Blueprint('inventory_bp', __name__)
api = Api(inventory_bp)

class Inventory(db.Model):
    """
    Represents a record of inventory movement/status for a specific product in a store.
    Recorded by a Clerk.
    """
    __tablename__ = 'inventory_records'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    clerk_id = db.Column(db.Integer, db.ForeignKey('clerks.id', ondelete='SET NULL'), nullable=True) 

    quantity_received = db.Column(db.Integer, nullable=False)
    items_in_stock = db.Column(db.Integer, nullable=False)
    items_spoilt = db.Column(db.Integer, default=0, nullable=False)
    payment_status = db.Column(db.Boolean, default=False, nullable=False) 

    
    buying_price_at_record = db.Column(db.Float, nullable=False)
    selling_price_at_record = db.Column(db.Float, nullable=False)

    date_recorded = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Inventory Record {self.id} for Product {self.product_id} in Store {self.store_id}>'

    def to_dict(self):
        
        product = Product.query.get(self.product_id)
        store = Store.query.get(self.store_id)
        clerk = Clerk.query.get(self.clerk_id)

        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': product.name if product else None,
            'store_id': self.store_id,
            'store_name': store.name if store else None,
            'clerk_id': self.clerk_id,
            'clerk_username': clerk.username if clerk else None,
            'quantity_received': self.quantity_received,
            'items_in_stock': self.items_in_stock,
            'items_spoilt': self.items_spoilt,
            'payment_status': self.payment_status,
            'buying_price_at_record': self.buying_price_at_record,
            'selling_price_at_record': self.selling_price_at_record,
            'date_recorded': self.date_recorded.isoformat() if self.date_recorded else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

 

class InventoryListResource(Resource):
    """
    Handles listing all inventory records and creating new records.
    Clerks can create records. Merchant, Admin, Clerk can view records.
    """
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin', 'clerk']:
            return {'message': 'Authentication required to view inventory records'}, 403

        query = Inventory.query

        if user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin:
                return {'message': 'Admin not found'}, 404
            if admin.store_id: 
                query = query.filter_by(store_id=admin.store_id)
            else: 
                return {'message': 'Admin not assigned to a store. Cannot view specific inventory records.'}, 403
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk:
                return {'message': 'Clerk not found'}, 404
            
            query = query.filter_by(clerk_id=current_user_id)
        
        inventory_records = query.all()
        return {'inventory_records': [record.to_dict() for record in inventory_records]}, 200

    @jwt_required()
    @clerk_required() 
    def post(self):
        current_clerk_id = get_jwt_identity()
        clerk = Clerk.query.get(current_clerk_id)
        if not clerk:
            return {'message': 'Clerk not found'}, 404 

        data = request.get_json()
        product_id = data.get('product_id')
        store_id = data.get('store_id')
        quantity_received = data.get('quantity_received')
        items_spoilt = data.get('items_spoilt', 0) 
        payment_status = data.get('payment_status', False) 

        if not all([product_id, store_id, quantity_received is not None]):
            return {'message': 'Missing required fields: product_id, store_id, quantity_received'}, 400

        
        try:
            product_id = int(product_id)
            store_id = int(store_id)
            quantity_received = int(quantity_received)
            items_spoilt = int(items_spoilt)
            if quantity_received < 0 or items_spoilt < 0:
                return {'message': 'Quantities cannot be negative'}, 400
        except ValueError:
            return {'message': 'product_id, store_id, quantities must be valid numbers'}, 400

        
        product = Product.query.get(product_id)
        if not product:
            return {'message': f'Product with ID {product_id} not found'}, 404

        store = Store.query.get(store_id)
        if not store:
            return {'message': f'Store with ID {store_id} not found'}, 404

        
        if clerk.store_id and clerk.store_id != store_id:
            return {'message': 'Clerk is not assigned to this store'}, 403
       
        try:
            new_record = Inventory(
                product_id=product_id,
                store_id=store_id,
                clerk_id=current_clerk_id,
                quantity_received=quantity_received,
                items_in_stock=quantity_received - items_spoilt, 
                items_spoilt=items_spoilt,
                payment_status=payment_status,
                buying_price_at_record=product.buying_price, 
                selling_price_at_record=product.selling_price
            )
            db.session.add(new_record)
            db.session.commit()
            return {'message': 'Inventory record created successfully', 'record': new_record.to_dict()}, 201
        except Exception as e:
            db.session.rollback()
            print(f"Error creating inventory record: {e}")
            return {'message': 'An internal server error occurred during record creation.'}, 500

class InventoryResource(Resource):
    """
    Handles operations on a single inventory record (get, update, delete).
    Only Merchant can delete. Admin can update payment status. Clerk can update stock/spoilt.
    """
    @jwt_required()
    def get(self, record_id):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        record = Inventory.query.get(record_id)
        if not record:
            return {'message': 'Inventory record not found'}, 404

       
        if user_type == 'merchant':
           
            pass
        elif user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin or (admin.store_id and admin.store_id != record.store_id):
                return {'message': 'Unauthorized to view this inventory record'}, 403
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk or clerk.id != record.clerk_id: 
                return {'message': 'Unauthorized to view this inventory record'}, 403
        else:
            return {'message': 'Authentication required to view inventory record'}, 403

        return {'inventory_record': record.to_dict()}, 200

    @jwt_required()
    def put(self, record_id):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        record = Inventory.query.get(record_id)
        if not record:
            return {'message': 'Inventory record not found'}, 404

        data = request.get_json()

        
        if user_type == 'merchant':
            
            pass
        elif user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin or (admin.store_id and admin.store_id != record.store_id):
                return {'message': 'Unauthorized to update this inventory record'}, 403
            
            if any(key in data for key in ['quantity_received', 'items_in_stock', 'items_spoilt', 'buying_price_at_record', 'selling_price_at_record']):
                return {'message': 'Admins can only update payment status of inventory records'}, 403
            if 'payment_status' in data:
                record.payment_status = data['payment_status']
            else:
                return {'message': 'No valid fields for Admin to update provided'}, 400
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk or clerk.id != record.clerk_id:
                return {'message': 'Unauthorized to update this inventory record'}, 403
            
            if 'payment_status' in data or 'quantity_received' in data or 'buying_price_at_record' in data or 'selling_price_at_record' in data:
                return {'message': 'Clerks can only update stock and spoilt items in inventory records'}, 403

            if 'items_in_stock' in data:
                try:
                    record.items_in_stock = int(data['items_in_stock'])
                    if record.items_in_stock < 0:
                        return {'message': 'Items in stock cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Items in stock must be a valid number'}, 400
            if 'items_spoilt' in data:
                try:
                    record.items_spoilt = int(data['items_spoilt'])
                    if record.items_spoilt < 0:
                        return {'message': 'Items spoilt cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Items spoilt must be a valid number'}, 400
            if not ('items_in_stock' in data or 'items_spoilt' in data):
                return {'message': 'No valid fields for Clerk to update provided'}, 400
        else:
            return {'message': 'Unauthorized to update this inventory record'}, 403

       
        if user_type == 'merchant':
            if 'quantity_received' in data:
                try:
                    record.quantity_received = int(data['quantity_received'])
                    if record.quantity_received < 0:
                        return {'message': 'Quantity received cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Quantity received must be a valid number'}, 400
            if 'items_in_stock' in data:
                try:
                    record.items_in_stock = int(data['items_in_stock'])
                    if record.items_in_stock < 0:
                        return {'message': 'Items in stock cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Items in stock must be a valid number'}, 400
            if 'items_spoilt' in data:
                try:
                    record.items_spoilt = int(data['items_spoilt'])
                    if record.items_spoilt < 0:
                        return {'message': 'Items spoilt cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Items spoilt must be a valid number'}, 400
            if 'payment_status' in data:
                record.payment_status = data['payment_status']
            if 'buying_price_at_record' in data:
                try:
                    record.buying_price_at_record = float(data['buying_price_at_record'])
                    if record.buying_price_at_record < 0:
                        return {'message': 'Buying price cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Buying price must be a valid number'}, 400
            if 'selling_price_at_record' in data:
                try:
                    record.selling_price_at_record = float(data['selling_price_at_record'])
                    if record.selling_price_at_record < 0:
                        return {'message': 'Selling price cannot be negative'}, 400
                except ValueError:
                    return {'message': 'Selling price must be a valid number'}, 400

        try:
            db.session.commit()
            return {'message': 'Inventory record updated successfully', 'record': record.to_dict()}, 200
        except Exception as e:
            db.session.rollback()
            print(f"Error updating inventory record: {e}")
            return {'message': 'An internal server error occurred during record update.'}, 500

    @jwt_required()
    @merchant_required() 
    def delete(self, record_id):
        record = Inventory.query.get(record_id)
        if not record:
            return {'message': 'Inventory record not found'}, 404

        try:
            db.session.delete(record)
            db.session.commit()
            return {'message': 'Inventory record deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting inventory record: {e}")
            return {'message': 'An internal server error occurred during record deletion.'}, 500


api.add_resource(InventoryListResource, '/')
api.add_resource(InventoryResource, '/<int:record_id>')

