from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user_models import Merchant, Admin, Clerk
from app.auth.permissions import merchant_required, admin_required, clerk_required
from datetime import datetime


product_bp = Blueprint('product_bp', __name__)
api = Api(product_bp)

class Product(db.Model):
    """
    Represents a product item available in the inventory system.
    """
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    buying_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchants.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
    inventories = db.relationship('Inventory', backref='product', lazy=True)
   

    def __repr__(self):
        return f'<Product {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'buying_price': self.buying_price,
            'selling_price': self.selling_price,
            'merchant_id': self.merchant_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ProductListResource(Resource):
    @jwt_required()
    def get(self):
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin', 'clerk']:
            return {'message': 'Authentication required to view products'}, 403

        products = Product.query.all()
        return {'products': [product.to_dict() for product in products]}, 200

    @jwt_required()
    def post(self):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin']:
            return {'message': 'Merchant or Admin access required to create products'}, 403

        data = request.get_json()
        name = data.get('name')
        description = data.get('description')
        buying_price = data.get('buying_price')
        selling_price = data.get('selling_price')

        if not all([name, buying_price, selling_price is not None]):
            return {'message': 'Missing required fields: name, buying_price, selling_price'}, 400

        try:
            buying_price = float(buying_price)
            selling_price = float(selling_price)
            if buying_price < 0 or selling_price < 0:
                return {'message': 'Prices cannot be negative'}, 400
        except ValueError:
            return {'message': 'Buying and selling prices must be valid numbers'}, 400

        if user_type == 'merchant':
            product_merchant_id = current_user_id
        elif user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin:
                return {'message': 'Admin not found for product creation'}, 404
            product_merchant_id = admin.merchant_id
        else:
            return {'message': 'Unauthorized to create products'}, 403


        try:
            new_product = Product(
                name=name,
                description=description,
                buying_price=buying_price,
                selling_price=selling_price,
                merchant_id=product_merchant_id
            )
            db.session.add(new_product)
            db.session.commit()
            return {'message': 'Product created successfully', 'product': new_product.to_dict()}, 201
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Product with this name already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error creating product: {e}")
            return {'message': 'An internal server error occurred during product creation.'}, 500

class ProductResource(Resource):
    @jwt_required()
    def get(self, product_id):
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin', 'clerk']:
            return {'message': 'Authentication required to view product'}, 403

        product = Product.query.get(product_id)
        if not product:
            return {'message': 'Product not found'}, 404

        return {'product': product.to_dict()}, 200

    @jwt_required()
    def put(self, product_id):
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        if user_type not in ['merchant', 'admin']:
            return {'message': 'Merchant or Admin access required to update products'}, 403

        product = Product.query.get(product_id)
        if not product:
            return {'message': 'Product not found'}, 404

        if user_type == 'merchant':
            if product.merchant_id != current_user_id:
                return {'message': 'Unauthorized to update this product'}, 403
        elif user_type == 'admin':
            admin = Admin.query.get(current_user_id)
            if not admin or product.merchant_id != admin.merchant_id:
                return {'message': 'Unauthorized to update this product'}, 403


        data = request.get_json()
        name = data.get('name', product.name)
        description = data.get('description', product.description)
        buying_price = data.get('buying_price', product.buying_price)
        selling_price = data.get('selling_price', product.selling_price)
        is_active = data.get('is_active', product.is_active)

        if name:
            product.name = name
        if description is not None:
            product.description = description

        if buying_price is not None:
            try:
                buying_price = float(buying_price)
                if buying_price < 0:
                    return {'message': 'Buying price cannot be negative'}, 400
                product.buying_price = buying_price
            except ValueError:
                return {'message': 'Buying price must be a valid number'}, 400

        if selling_price is not None:
            try:
                selling_price = float(selling_price)
                if selling_price < 0:
                    return {'message': 'Selling price cannot be negative'}, 400
                product.selling_price = selling_price
            except ValueError:
                return {'message': 'Selling price must be a valid number'}, 400

        if isinstance(is_active, bool):
            product.is_active = is_active

        try:
            db.session.commit()
            return {'message': 'Product updated successfully', 'product': product.to_dict()}, 200
        except IntegrityError:
            db.session.rollback()
            return {'message': 'Product with this name already exists'}, 409
        except Exception as e:
            db.session.rollback()
            print(f"Error updating product: {e}")
            return {'message': 'An internal server error occurred during product update.'}, 500

    @jwt_required()
    @merchant_required()
    def delete(self, product_id):
        current_user_id = get_jwt_identity()
        product = Product.query.get(product_id)
        if not product:
            return {'message': 'Product not found'}, 404

        if product.merchant_id != current_user_id:
            return {'message': 'Unauthorized to delete this product'}, 403

        try:
            db.session.delete(product)
            db.session.commit()
            return {'message': 'Product deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting product: {e}")
            return {'message': 'An internal server error occurred during product deletion.'}, 500


api.add_resource(ProductListResource, '/')
api.add_resource(ProductResource, '/<int:product_id>')


