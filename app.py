import os
import random
from datetime import datetime, timedelta

from flask import Flask
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from config import Config
from extensions import db, mail, csrf, limiter, login_manager
from models import User, Account, Transaction, Notification
from routes.auth import auth_bp
from routes.main import main_bp


app = Flask(__name__)
app.config.from_object(Config)


app.config["RATELIMIT_STORAGE_URI"] = app.config.get(
    "LIMITER_STORAGE_URI",
    "memory://"
)


app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


db.init_app(app)
mail.init_app(app)
csrf.init_app(app)
limiter.init_app(app)
login_manager.init_app(app)


login_manager.login_view = "main.home"
login_manager.login_message_category = "warning"


app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_unread_notifications():
    if current_user.is_authenticated:
        unread_notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
    else:
        unread_notifications = 0

    return dict(unread_notifications=unread_notifications)


@app.after_request
def add_security_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


def random_date(start, end):
    delta = end - start
    return start + timedelta(seconds=random.randint(0, max(1, int(delta.total_seconds()))))


def unique_customer_id():
    while True:
        customer_id = f"NS-DEMO-{random.randint(100000, 999999)}"
        if not User.query.filter_by(customer_id=customer_id).first():
            return customer_id


def unique_account_number():
    while True:
        account_number = f"AC-DEMO-{random.randint(1000000000, 9999999999)}"
        if not Account.query.filter_by(account_number=account_number).first():
            return account_number


def seed_demo_data():
    
    with app.app_context():
        db.create_all()

        demo_customer_id = "BAS-UB-784512"
        demo_email = "sewilliams850@gmail.com"
        demo_full_name = "Joshua A. Perez"
        demo_password = "sewilly223"
        demo_account_number = "AC-BOA-241908"
        starting_balance_cents = 128400000

        today = datetime.utcnow()
        start_year = today.year if today.month >= 2 else today.year - 1
        start = datetime(start_year, 2, 1)
        end = today

       
        user = User.query.filter_by(customer_id=demo_customer_id).first()
        if not user:
            user = User.query.filter_by(email=demo_email).first()

        if user:
            user.customer_id = demo_customer_id
            user.full_name = demo_full_name
            user.email = demo_email
            user.password_hash = generate_password_hash(demo_password)
            user.email_verified = True
        else:
            user = User(
                customer_id=demo_customer_id,
                full_name=demo_full_name,
                email=demo_email,
                password_hash=generate_password_hash(demo_password),
                email_verified=True
            )
            db.session.add(user)
            db.session.flush()

        
        account = user.account
        if not account:
            existing_account = Account.query.filter_by(account_number=demo_account_number).first()
            if existing_account and existing_account.user_id != user.id:
                demo_account_number = unique_account_number()

            account = Account(
                user_id=user.id,
                bank_name="Bank of America",
                account_number=demo_account_number,
                balance_cents=starting_balance_cents
            )
            db.session.add(account)
            db.session.flush()
        else:
            account.bank_name = "Bank of America"
            account.account_number = demo_account_number
            if account.balance_cents == 0:
                account.balance_cents = starting_balance_cents

        
        if Transaction.query.filter_by(account_id=account.id).count() == 0:
            sample_transactions = [
                
                (20000000, "debit", "Atlas Precision Manufacturing Co.", "Purchase of New Products"),
                (36500000, "debit", "Summit Industrial Components LLC", "Inventory Expansion"),
                (24800000, "debit", "Pioneer Fabrication Group", "Equipment Procurement"),
                (41750000, "debit", "North Ridge Materials Ltd.", "Raw Materials Procurement"),
                (15900000, "debit", "Crescent Assembly Systems", "Vendor Settlement"),

                
                (52000000, "credit", "Meridian Industrial Supply Inc.", "Client Payment Received"),
                (31000000, "credit", "Keystone Fabrication Partners", "Invoice Settlement"),
                (69000000, "credit", "Apex Components Manufacturing LLC", "Contract Deposit"),
            ]

            for amount_cents, tx_type, receiver, purpose in sample_transactions:
                db.session.add(Transaction(
                    account_id=account.id,
                    amount_cents=amount_cents,
                    tx_type=tx_type,
                    receiver=receiver,
                    purpose=purpose,
                    status="completed",
                    created_at=random_date(start, end)
                ))

        
        if Notification.query.filter_by(user_id=user.id).count() == 0:
            notifications = [
                Notification(
                    user_id=user.id,
                    category="security",
                    title="Welcome to Bank of America",
                    message="Your account has been created successfully.",
                    is_read=False,
                    created_at=datetime.utcnow() - timedelta(hours=2)
                ),
                Notification(
                    user_id=user.id,
                    category="transfer",
                    title="Pending transfer authorization",
                    message="A transfer is waiting for OTP verification.",
                    is_read=False,
                    created_at=datetime.utcnow() - timedelta(days=1)
                ),
                Notification(
                    user_id=user.id,
                    category="system",
                    title="Statement ready",
                    message="Your latest account statement is now available for review.",
                    is_read=False,
                    created_at=datetime.utcnow() - timedelta(days=3)
                ),
            ]
            db.session.add_all(notifications)

        db.session.commit()

        print("Data seeded successfully.")
        print(f"User ID: {user.customer_id}")
        print(f"Email: {user.email}")
        print(f"Password: {demo_password}")
        print(f"Account Number: {account.account_number}")


@app.cli.command("init-db")
def init_db_command():
    with app.app_context():
        db.create_all()
    print("Database initialized.")


if __name__ == "__main__":
    
    if os.getenv("SEED_DEMO_DATA", "false").lower() == "true":
        seed_demo_data()

    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)