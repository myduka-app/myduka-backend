from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import calendar 

from app import db
from app.models.user_models import Merchant, Admin, Clerk
from app.models.products import Product
from app.models.store import Store
from app.models.inventory import Inventory
from app.models.transactions import Transaction
from app.models.supply_request import SupplyRequest
from app.auth.permissions import merchant_required, admin_required


report_bp = Blueprint('report_bp', __name__)
api = Api(report_bp)

class BaseReportResource(Resource):
    """
    Base class for report resources, handling common permission checks and date filtering.
    """
    decorators = [jwt_required()]

    def get_authorized_query(self, model_class, user_id, user_type):
        query = model_class.query
        if user_type == 'merchant':
            
            pass
        elif user_type == 'admin':
            admin = Admin.query.get(user_id)
            if not admin:
                return None, {'message': 'Admin not found'}, 404
            if not admin.store_id:
                return None, {'message': 'Admin not assigned to a store. Cannot generate store-specific reports.'}, 403
          
            query = query.filter_by(store_id=admin.store_id)
        else:
            return None, {'message': 'Unauthorized to view reports'}, 403
        return query, None, None

    def apply_date_filter(self, query, date_column, start_date_str, end_date_str):
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(date_column >= start_date)
            except ValueError:
                return None, {'message': 'Invalid start_date format. Use YYYY-MM-DD'}, 400
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) 
                query = query.filter(date_column < end_date)
            except ValueError:
                return None, {'message': 'Invalid end_date format. Use YYYY-MM-DD'}, 400
        return query, None, None

class SalesReportResource(BaseReportResource):
    """
    Generates sales reports (weekly, monthly, annual).
    """
    def get(self):
        user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        query, error_response, status_code = self.get_authorized_query(Transaction, user_id, user_type)
        if error_response:
            return error_response, status_code

        
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        report_type = request.args.get('type', 'daily').lower() 

        query, error_response, status_code = self.apply_date_filter(query, Transaction.transaction_date, start_date_str, end_date_str)
        if error_response:
            return error_response, status_code

        
        if not start_date_str and not end_date_str:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            query = query.filter(Transaction.transaction_date >= start_date, Transaction.transaction_date <= end_date)


        
        if report_type == 'daily':
            results = query.with_entities(
                func.date(Transaction.transaction_date).label('date'),
                func.sum(Transaction.total_revenue).label('total_revenue'),
                func.sum(Transaction.quantity_sold).label('total_quantity_sold')
            ).group_by(func.date(Transaction.transaction_date)).order_by('date').all()
            report_data = [{'date': r.date.isoformat(), 'total_revenue': r.total_revenue, 'total_quantity_sold': r.total_quantity_sold} for r in results]
        elif report_type == 'weekly':
            results = query.with_entities(
                func.extract('year', Transaction.transaction_date).label('year'),
                func.extract('week', Transaction.transaction_date).label('week'),
                func.sum(Transaction.total_revenue).label('total_revenue'),
                func.sum(Transaction.quantity_sold).label('total_quantity_sold')
            ).group_by('year', 'week').order_by('year', 'week').all()
            report_data = [{'year': int(r.year), 'week': int(r.week), 'total_revenue': r.total_revenue, 'total_quantity_sold': r.total_quantity_sold} for r in results]
        elif report_type == 'monthly':
            results = query.with_entities(
                func.extract('year', Transaction.transaction_date).label('year'),
                func.extract('month', Transaction.transaction_date).label('month'),
                func.sum(Transaction.total_revenue).label('total_revenue'),
                func.sum(Transaction.quantity_sold).label('total_quantity_sold')
            ).group_by('year', 'month').order_by('year', 'month').all()
            report_data = [{'year': int(r.year), 'month': int(r.month), 'total_revenue': r.total_revenue, 'total_quantity_sold': r.total_quantity_sold} for r in results]
        elif report_type == 'annual':
            results = query.with_entities(
                func.extract('year', Transaction.transaction_date).label('year'),
                func.sum(Transaction.total_revenue).label('total_revenue'),
                func.sum(Transaction.quantity_sold).label('total_quantity_sold')
            ).group_by('year').order_by('year').all()
            report_data = [{'year': int(r.year), 'total_revenue': r.total_revenue, 'total_quantity_sold': r.total_quantity_sold} for r in results]
        else:
            return {'message': 'Invalid report type. Choose from daily, weekly, monthly, annual.'}, 400

        return {'report_type': report_type, 'data': report_data}, 200

class StockReportResource(BaseReportResource):
    """
    Generates stock level reports.
    """
    def get(self):
        user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        
        query, error_response, status_code = self.get_authorized_query(Inventory, user_id, user_type)
        if error_response:
            return error_response, status_code

        
        product_id = request.args.get('product_id', type=int)
        store_id = request.args.get('store_id', type=int)

        if product_id:
            query = query.filter_by(product_id=product_id)
        if store_id:
            query = query.filter_by(store_id=store_id)

       
        all_records = query.order_by(Inventory.date_recorded.desc()).all()

        current_stock = {}
        for record in all_records:
            key = (record.product_id, record.store_id)
            if key not in current_stock: 
                product = Product.query.get(record.product_id)
                store = Store.query.get(record.store_id)
                current_stock[key] = {
                    'product_id': record.product_id,
                    'product_name': product.name if product else None,
                    'store_id': record.store_id,
                    'store_name': store.name if store else None,
                    'items_in_stock': record.items_in_stock,
                    'last_updated': record.date_recorded.isoformat() if record.date_recorded else None
                }

        report_data = list(current_stock.values())
        return {'report_type': 'current_stock', 'data': report_data}, 200

class SpoiltItemsReportResource(BaseReportResource):
    """
    Generates reports on spoilt items.
    """
    def get(self):
        user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        query, error_response, status_code = self.get_authorized_query(Inventory, user_id, user_type)
        if error_response:
            return error_response, status_code

        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query, error_response, status_code = self.apply_date_filter(query, Inventory.date_recorded, start_date_str, end_date_str)
        if error_response:
            return error_response, status_code

        
        query = query.filter(Inventory.items_spoilt > 0)

        results = query.with_entities(
            Product.name.label('product_name'),
            Store.name.label('store_name'),
            func.sum(Inventory.items_spoilt).label('total_spoilt_items'),
            func.min(Inventory.date_recorded).label('first_record_date'),
            func.max(Inventory.date_recorded).label('last_record_date')
        ).join(Product).join(Store).group_by(Product.name, Store.name).all()

        report_data = [{
            'product_name': r.product_name,
            'store_name': r.store_name,
            'total_spoilt_items': r.total_spoilt_items,
            'first_record_date': r.first_record_date.isoformat() if r.first_record_date else None,
            'last_record_date': r.last_record_date.isoformat() if r.last_record_date else None
        } for r in results]

        return {'report_type': 'spoilt_items', 'data': report_data}, 200

class PaymentStatusReportResource(BaseReportResource):
    """
    Generates reports on payment status of received products (from Inventory records).
    """
    def get(self):
        user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        query, error_response, status_code = self.get_authorized_query(Inventory, user_id, user_type)
        if error_response:
            return error_response, status_code

        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        payment_status_filter = request.args.get('payment_status') 

        query, error_response, status_code = self.apply_date_filter(query, Inventory.date_recorded, start_date_str, end_date_str)
        if error_response:
            return error_response, status_code

        if payment_status_filter:
            if payment_status_filter.lower() == 'paid':
                query = query.filter_by(payment_status=True)
            elif payment_status_filter.lower() == 'unpaid':
                query = query.filter_by(payment_status=False)
            else:
                return {'message': 'Invalid payment_status filter. Use "paid" or "unpaid".'}, 400

        results = query.with_entities(
            Product.name.label('product_name'),
            Store.name.label('store_name'),
            Inventory.payment_status.label('payment_status'),
            func.sum(Inventory.quantity_received).label('total_quantity_received'),
            func.sum(Inventory.buying_price_at_record * Inventory.quantity_received).label('total_cost')
        ).join(Product).join(Store).group_by(Product.name, Store.name, Inventory.payment_status).all()

        report_data = [{
            'product_name': r.product_name,
            'store_name': r.store_name,
            'payment_status': 'Paid' if r.payment_status else 'Unpaid',
            'total_quantity_received': r.total_quantity_received,
            'total_cost': r.total_cost
        } for r in results]

        return {'report_type': 'payment_status', 'data': report_data}, 200



api.add_resource(SalesReportResource, '/sales')
api.add_resource(StockReportResource, '/stock')
api.add_resource(SpoiltItemsReportResource, '/spoilt-items')
api.add_resource(PaymentStatusReportResource, '/payment-status')

