from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_cors import CORS
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.config import config 

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()
cors = CORS()
migrate = Migrate()
bcrypt = Bcrypt()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

def create_app(config_name='default'): 
    """
    Application factory function
    """
    app = Flask(__name__)
    app.config.from_object(config[config_name]) 

    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    # Configure CORS to allow requests from frontend origins with credentials support
    cors.init_app(app, resources={r"/*": {"origins": app.config['CORS_ORIGINS'], "supports_credentials": True}})
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    limiter.init_app(app)

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    # Check if the app is running
    @app.route('/')
    def index():
        return jsonify({"message": "MyDuka Backend is running!"}), 200

    return app

def register_blueprints(app):
    """
    Register all blueprints with the application
    """
    from app.models.merchant import merchant_bp
    app.register_blueprint(merchant_bp, url_prefix='/merchant')

    from app.models.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.models.clerk import clerk_bp
    app.register_blueprint(clerk_bp, url_prefix='/clerk')

    # Authentication Blueprints
    from app.auth.login import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.auth.invitations import invitations_bp
    app.register_blueprint(invitations_bp, url_prefix='/auth')

    # Store Blueprint
    from app.models.store import store_bp
    app.register_blueprint(store_bp, url_prefix='/store')

    # Product Blueprint
    from app.models.products import product_bp
    app.register_blueprint(product_bp, url_prefix='/product')

    # Inventory Blueprint
    from app.models.inventory import inventory_bp
    app.register_blueprint(inventory_bp, url_prefix='/inventory')

    # Transaction Blueprint
    from app.models.transactions import transaction_bp
    app.register_blueprint(transaction_bp, url_prefix='/transaction')

    # Supply Request Blueprint
    from app.models.supply_request import supply_request_bp
    app.register_blueprint(supply_request_bp, url_prefix='/supply-requests')

    # Report Blueprint
    from app.models.reports import report_bp
    app.register_blueprint(report_bp, url_prefix='/reports')

def register_error_handlers(app):
    """
    Register error handlers
    """
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request'}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden'}), 403

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500