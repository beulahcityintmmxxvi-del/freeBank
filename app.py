import os
import random
from datetime import datetime, timedelta

from flask import Flask
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from config import Config
from flask_wtf import CSRFProtect

from extensions import db, mail, limiter, login_manager
from models import User, Account, Transaction, Notification

from routes.auth import auth_bp
from routes.main import main_bp

app = Flask(__name__)

app.config.from_object(Config)

app.secret_key = os.getenv("SECRET_KEY", "isuiuu89ugauit87tiq8")

app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    WTF_CSRF_ENABLED=True,
    WTF_CSRF_SSL_STRICT=False,
    RATELIMIT_STORAGE_URI=app.config.get("LIMITER_STORAGE_URI", "memory://")
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

db.init_app(app)
mail.init_app(app)
limiter.init_app(app)
login_manager.init_app(app)

csrf = CSRFProtect(app)

login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

@app.context_processor
def inject_unread_notifications():
    if current_user.is_authenticated:
        count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
    else:
        count = 0

    return dict(unread_notifications=count)


@app.after_request
def add_security_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)

def random_date(start, end):
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def unique_customer_id():
    while True:
        cid = f"NS-DEMO-{random.randint(100000, 999999)}"
        if not User.query.filter_by(customer_id=cid).first():
            return cid


def unique_account_number():
    while True:
        acc = f"AC-DEMO-{random.randint(1000000000, 9999999999)}"
        if not Account.query.filter_by(account_number=acc).first():
            return acc


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
        start = datetime(today.year, 2, 1)

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
            existing = Account.query.filter_by(account_number=demo_account_number).first()
            if existing:
                demo_account_number = unique_account_number()

            account = Account(
                user_id=user.id,
                bank_name="Bank of America",
                account_number=demo_account_number,
                balance_cents=starting_balance_cents
            )
            db.session.add(account)
        else:
            account.balance_cents = account.balance_cents or starting_balance_cents

        db.session.commit()

@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.create_all()
    print("Database initialized.")

if __name__ == "__main__":
    
    if os.getenv("SEED_DEMO_DATA", "false").lower() == "true":
        seed_demo_data()

    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)