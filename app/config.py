import os
from datetime import timedelta
from dotenv import load_dotenv


load_dotenv()

class Config:
    """
    Base configuration class
    """
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    
    #
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://myduka_user:password@localhost/myduka_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
   
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-string-change-this'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Invitation token expiry in hours
    INVITATION_TOKEN_EXPIRY = int(os.environ.get('INVITATION_TOKEN_EXPIRY', 24))
    
    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Pagination
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    
    # Redis configuration (for session management and caching)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    
    # Rate limiting configuration
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '1000 per hour')
    
    # Application-specific settings
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'MyDuka')
    SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'support@myduka.com')

class DevelopmentConfig(Config):
    """
    Development configuration
    """
    DEBUG = True

class TestingConfig(Config):
    """
    Testing configuration
    """
    TESTING = True
    WTF_CSRF_ENABLED = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=1)

class ProductionConfig(Config):
    """
    Production configuration
    """
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}