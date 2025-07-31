

from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user_models import Merchant, Admin, Clerk
from app.models.products import Product
from app.models.store import Store
from app.models.inventory import Inventory 
from app.auth.permissions import merchant_required, admin_required, clerk_required
from datetime import datetime


transaction_bp = Blueprint('transaction_bp', __name__)
api = Api(transaction_bp)

class Transaction(db.Model):
    """
    Represents a sales transaction recorded by a Clerk.
    """
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    clerk_id = db.Column(db.Integer, db.ForeignKey('clerks.id', ondelete='SET NULL'), nullable=True)

    quantity_sold = db.Column(db.Integer, nullable=False)
    selling_price_at_transaction = db.Column(db.Float, nullable=False) 
    total_revenue = db.Column(db.Float, nullable=False) 

    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Transaction {self.id} for Product {self.product_id} in Store {self.store_id}>'

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
            'quantity_sold': self.quantity_sold,
            'selling_price_at_transaction': self.selling_price_at_transaction,
            'total_revenue': self.total_revenue,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }



class TransactionListResource(Resource):
    """
    Handles listing all transactions and creating new transactions.
    Clerks can create transactions. Merchant, Admin, Clerk can view transactions.
    """
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin', 'clerk']:
            return {'message': 'Authentication required to view transactions'}, 403

        query = Transaction.query

        if user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin:
                return {'message': 'Admin not found'}, 404
            if admin.store_id: 
                query = query.filter_by(store_id=admin.store_id)
            else:
                return {'message': 'Admin not assigned to a store. Cannot view transactions.'}, 403
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk:
                return {'message': 'Clerk not found'}, 404
           
            query = query.filter_by(clerk_id=current_user_id)
        

        transactions = query.all()
        return {'transactions': [transaction.to_dict() for transaction in transactions]}, 200

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
        quantity_sold = data.get('quantity_sold')

        if not all([product_id, store_id, quantity_sold is not None]):
            return {'message': 'Missing required fields: product_id, store_id, quantity_sold'}, 400

        
        try:
            product_id = int(product_id)
            store_id = int(store_id)
            quantity_sold = int(quantity_sold)
            if quantity_sold <= 0:
                return {'message': 'Quantity sold must be positive'}, 400
        except ValueError:
            return {'message': 'product_id, store_id, quantity_sold must be valid numbers'}, 400

        
        product = Product.query.get(product_id)
        if not product:
            return {'message': f'Product with ID {product_id} not found'}, 404

        store = Store.query.get(store_id)
        if not store:
            return {'message': f'Store with ID {store_id} not found'}, 404

        
        if clerk.store_id and clerk.store_id != store_id:
            return {'message': 'Clerk is not assigned to this store'}, 403

        
        latest_inventory_record = Inventory.query.filter_by(
            product_id=product_id,
            store_id=store_id
        ).order_by(Inventory.date_recorded.desc()).first()

        if not latest_inventory_record or latest_inventory_record.items_in_stock < quantity_sold:
            return {'message': 'Insufficient stock for this product in this store'}, 400

        try:
            # Create the transaction record
            selling_price = product.selling_price 
            total_revenue = selling_price * quantity_sold

            new_transaction = Transaction(
                product_id=product_id,
                store_id=store_id,
                clerk_id=current_clerk_id,
                quantity_sold=quantity_sold,
                selling_price_at_transaction=selling_price,
                total_revenue=total_revenue
            )
            db.session.add(new_transaction)

            # Update the latest inventory record's stock
            latest_inventory_record.items_in_stock -= quantity_sold
            db.session.add(latest_inventory_record) 

            db.session.commit()
            return {'message': 'Transaction recorded successfully', 'transaction': new_transaction.to_dict()}, 201
        except Exception as e:
            db.session.rollback()
            print(f"Error creating transaction: {e}")
            return {'message': 'An internal server error occurred during transaction creation.'}, 500

class TransactionResource(Resource):
    """
    Handles operations on a single transaction record (get, delete).
    Only Merchant can delete. No updates allowed for transactions.
    """
    @jwt_required()
    def get(self, transaction_id):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return {'message': 'Transaction not found'}, 404

        # Permission checks for viewing a single record
        if user_type == 'merchant':
            
            pass
        elif user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin or (admin.store_id and admin.store_id != transaction.store_id):
                return {'message': 'Unauthorized to view this transaction record'}, 403
        elif user_type == 'clerk':
            clerk = Clerk.query.get(current_user_id)
            if not clerk or clerk.id != transaction.clerk_id: 
                return {'message': 'Unauthorized to view this transaction record'}, 403
        else:
            return {'message': 'Authentication required to view transaction record'}, 403

        return {'transaction_record': transaction.to_dict()}, 200

    @jwt_required()
    @merchant_required() 
    def delete(self, transaction_id):
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return {'message': 'Transaction not found'}, 404

        try:
            
            db.session.delete(transaction)
            db.session.commit()
            return {'message': 'Transaction deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting transaction: {e}")
            return {'message': 'An internal server error occurred during transaction deletion.'}, 500


api.add_resource(TransactionListResource, '/')
api.add_resource(TransactionResource, '/<int:transaction_id>')