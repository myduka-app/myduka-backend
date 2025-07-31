import random
from datetime import datetime, timedelta
from faker import Faker
from flask.cli import with_appcontext
import click

from app import db, bcrypt
from app.models.user_models import Merchant, Admin, Clerk
from app.models.store import Store
from app.models.products import Product
from app.models.inventory import Inventory
from app.models.transactions import Transaction
from app.models.supply_request import SupplyRequest

fake = Faker()

@click.command('seed')
@with_appcontext
def seed_command():
    """Seeds the database with dummy data."""
    click.echo('Seeding database...')
    seed_data()
    click.echo('Database seeded!')

def seed_data():
    """Populates the database with sample data."""
    db.drop_all() # WARNING: This will delete all existing data! Use with caution.
    db.create_all()

    # --- 1. Create Merchant ---
    merchant_email = 'merchant@example.com'
    merchant = Merchant.query.filter_by(email=merchant_email).first()
    if not merchant:
        merchant = Merchant(
            username='supermerchant',
            email=merchant_email,
            is_active=True,
            is_superuser=True
        )
        merchant.password = 'Strong1234!'
        db.session.add(merchant)
        db.session.commit()
        click.echo(f"Created Merchant: {merchant.username}")
    else:
        click.echo(f"Merchant '{merchant.username}' already exists. Skipping creation.")

    # --- 2. Create Stores ---
    stores_data = [
        {'name': 'CBD Branch', 'location': 'Nairobi CBD'},
        {'name': 'Westlands Outlet', 'location': 'Westlands, Nairobi'},
        {'name': 'Karen Store', 'location': 'Karen, Nairobi'},
    ]
    created_stores = []
    for s_data in stores_data:
        store = Store.query.filter_by(name=s_data['name']).first()
        if not store:
            store = Store(
                name=s_data['name'],
                location=s_data['location'],
                merchant_id=merchant.id,
                is_active=True
            )
            db.session.add(store)
            created_stores.append(store)
            click.echo(f"Created Store: {store.name}")
    db.session.commit() # Commit stores to get their IDs

    # Refresh created_stores with committed objects
    created_stores = Store.query.filter(Store.name.in_([s['name'] for s in stores_data])).all()


    # --- 3. Create Admins and Assign to Stores ---
    num_admins = 3
    created_admins = []
    for i in range(num_admins):
        admin_email = f'admin{i+1}@example.com'
        admin = Admin.query.filter_by(email=admin_email).first()
        if not admin:
            admin_username = fake.user_name()
            admin = Admin(
                username=admin_username,
                email=admin_email,
                merchant_id=merchant.id,
                is_active=True
            )
            admin.password = 'AdminPassword123!'
            # Assign store to admin (round-robin)
            if created_stores:
                admin.store_id = created_stores[i % len(created_stores)].id
            db.session.add(admin)
            created_admins.append(admin)
            click.echo(f"Created Admin: {admin.username} (Store ID: {admin.store_id})")
    db.session.commit()

    # Refresh created_admins with committed objects
    created_admins = Admin.query.filter(Admin.email.in_([f'admin{i+1}@example.com' for i in range(num_admins)])).all()


    # --- 4. Create Clerks and Assign to Admins ---
    num_clerks_per_admin = 2
    created_clerks = []
    for admin in created_admins:
        for i in range(num_clerks_per_admin):
            clerk_email = f'clerk{admin.id}_{i+1}@example.com'
            clerk = Clerk.query.filter_by(email=clerk_email).first()
            if not clerk:
                clerk_username = fake.user_name()
                clerk = Clerk(
                    username=clerk_username,
                    email=clerk_email,
                    admin_id=admin.id,
                    store_id=admin.store_id, # Clerks inherit store_id from their admin
                    is_active=True
                )
                clerk.password = 'ClerkPassword123!'
                db.session.add(clerk)
                created_clerks.append(clerk)
                click.echo(f"Created Clerk: {clerk.username} (Admin ID: {admin.id}, Store ID: {clerk.store_id})")
    db.session.commit()

    # Refresh created_clerks with committed objects
    created_clerks = Clerk.query.all()


    # --- 5. Create Products ---
    products_data = [
        {'name': 'Laptop Pro X', 'description': 'High-performance laptop for professionals', 'buying_price': 800.00, 'selling_price': 1200.00},
        {'name': 'Wireless Mouse', 'description': 'Ergonomic wireless mouse', 'buying_price': 15.50, 'selling_price': 30.00},
        {'name': 'Mechanical Keyboard', 'description': 'RGB mechanical keyboard', 'buying_price': 60.00, 'selling_price': 100.00},
        {'name': 'USB-C Hub', 'description': '7-in-1 USB-C hub', 'buying_price': 25.00, 'selling_price': 45.00},
        {'name': 'External SSD 1TB', 'description': 'Portable 1TB SSD', 'buying_price': 90.00, 'selling_price': 150.00},
    ]
    created_products = []
    for p_data in products_data:
        product = Product.query.filter_by(name=p_data['name']).first()
        if not product:
            product = Product(
                name=p_data['name'],
                description=p_data['description'],
                buying_price=p_data['buying_price'],
                selling_price=p_data['selling_price'],
                merchant_id=merchant.id,
                is_active=True
            )
            db.session.add(product)
            created_products.append(product)
            click.echo(f"Created Product: {product.name}")
    db.session.commit()

    # Refresh created_products with committed objects
    created_products = Product.query.filter(Product.name.in_([p['name'] for p in products_data])).all()


    # --- 6. Generate Inventory Records, Transactions, and Supply Requests ---
    if not created_products or not created_stores or not created_clerks:
        click.echo("Not enough products, stores, or clerks to generate inventory/transactions/requests.")
        return

    for _ in range(20): # Generate 20 random inventory records
        product = random.choice(created_products)
        store = random.choice(created_stores)
        clerk = random.choice(created_clerks)

        # Ensure clerk is assigned to the store or has no store assigned
        if clerk.store_id and clerk.store_id != store.id:
            # Find a clerk assigned to this store, or one with no store_id
            eligible_clerks = [c for c in created_clerks if c.store_id == store.id or c.store_id is None]
            if not eligible_clerks: continue # Skip if no suitable clerk
            clerk = random.choice(eligible_clerks)
        elif clerk.store_id is None:
            # If clerk has no store_id, assign them to this store for this record
            clerk.store_id = store.id # Temporarily assign for this record, or update clerk permanently if desired
            db.session.add(clerk) # Mark clerk for update if their store_id changed

        qty_received = random.randint(50, 500)
        items_spoilt = random.randint(0, int(qty_received * 0.05)) # Up to 5% spoilt
        initial_stock = qty_received - items_spoilt
        payment_status = random.choice([True, False])
        record_date = fake.date_time_between(start_date='-1y', end_date='now')

        inventory_record = Inventory(
            product_id=product.id,
            store_id=store.id,
            clerk_id=clerk.id,
            quantity_received=qty_received,
            items_in_stock=initial_stock,
            items_spoilt=items_spoilt,
            payment_status=payment_status,
            buying_price_at_record=product.buying_price,
            selling_price_at_record=product.selling_price,
            date_recorded=record_date
        )
        db.session.add(inventory_record)
        click.echo(f"Created Inventory Record: Product {product.name}, Store {store.name}, Qty: {qty_received}, Stock: {initial_stock}")
    db.session.commit()

    # Generate Transactions (after inventory exists)
    all_inventory_records = Inventory.query.all()
    if not all_inventory_records:
        click.echo("No inventory records to generate transactions from.")
        return

    for _ in range(50): # Generate 50 random transactions
        record = random.choice(all_inventory_records)
        product = Product.query.get(record.product_id)
        store = Store.query.get(record.store_id)
        clerk = Clerk.query.get(record.clerk_id) # Use the clerk who recorded the inventory

        if not product or not store or not clerk: continue # Skip if related entities are missing

        qty_sold = random.randint(1, min(record.items_in_stock, 20)) # Sell up to 20 items or current stock
        if qty_sold == 0: continue # Skip if no stock to sell

        transaction_date = fake.date_time_between(start_date=record.date_recorded, end_date='now')

        transaction = Transaction(
            product_id=product.id,
            store_id=store.id,
            clerk_id=clerk.id,
            quantity_sold=qty_sold,
            selling_price_at_transaction=product.selling_price,
            total_revenue=qty_sold * product.selling_price,
            transaction_date=transaction_date
        )
        db.session.add(transaction)

        # Update stock in the inventory record
        record.items_in_stock -= qty_sold
        db.session.add(record) # Mark for update

        click.echo(f"Created Transaction: Product {product.name}, Store {store.name}, Sold: {qty_sold}, New Stock: {record.items_in_stock}")
    db.session.commit()

    # Generate Supply Requests
    for _ in range(15): # Generate 15 random supply requests
        product = random.choice(created_products)
        clerk = random.choice(created_clerks)
        store = Store.query.get(clerk.store_id) if clerk.store_id else random.choice(created_stores)

        if not store: continue # Skip if no store to link to

        qty_requested = random.randint(10, 200)
        request_date = fake.date_time_between(start_date='-6m', end_date='now')
        status = random.choice(['Pending', 'Approved', 'Declined', 'Fulfilled'])
        notes = fake.sentence()

        approved_by_admin = None
        response_date = None
        if status in ['Approved', 'Declined', 'Fulfilled'] and created_admins:
            approved_by_admin = random.choice(created_admins)
            response_date = fake.date_time_between(start_date=request_date, end_date='now')

        supply_request = SupplyRequest(
            product_id=product.id,
            store_id=store.id,
            requested_by_clerk_id=clerk.id,
            approved_by_admin_id=approved_by_admin.id if approved_by_admin else None,
            quantity_requested=qty_requested,
            status=status,
            notes=notes,
            request_date=request_date,
            response_date=response_date
        )
        db.session.add(supply_request)
        click.echo(f"Created Supply Request: Product {product.name}, Store {store.name}, Qty: {qty_requested}, Status: {status}")
    db.session.commit()