

from app.database import db
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite"""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def init_db(app):
    """Initialize database with application context"""
    with app.app_context():
       
        db.create_all()
        
       
        from app.models import merchant, admin, clerk, store, product, inventory, transaction, supply_request, report
        
        print("Database initialized successfully!")

def drop_db(app):
    """Drop all database tables"""
    with app.app_context():
        db.drop_all()
        print("Database dropped successfully!")

def reset_db(app):
    """Reset database - drop and recreate all tables"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset successfully!")