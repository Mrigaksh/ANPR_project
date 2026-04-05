import os
import sys
import datetime as dt
from dotenv import load_dotenv

# Force load .env from the same directory as this script
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)

from app import create_app
from models import db, User
from werkzeug.security import generate_password_hash
import datetime

app = create_app()

print(f"\n{'='*50}")
print(f"Using Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
print(f"{'='*50}\n")

with app.app_context():
    try:
        # Step 1: Create all tables
        print("Creating database tables...")
        db.create_all()
        print("[OK] Tables created successfully!\n")

        # Step 2: Check/create admin user
        print("Checking for admin user...")
        admin_user = User.query.filter_by(username='admin').first()
        
        if admin_user:
            # Update admin password to ensure it's correct
            print("[INFO] Admin user already exists. Resetting password...")
            admin_user.password_hash = generate_password_hash('admin123', method='pbkdf2:sha256')
            db.session.commit()
            print("[OK] Admin password reset to 'admin123'.")
        else:
            # Create fresh admin
            print("[INFO] Admin user not found. Creating admin...")
            hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin = User(
                username='admin',
                email='admin@anpr.com',
                password_hash=hashed_password,
                role='admin',
                is_active=True,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print("[OK] Admin user created successfully!")
        
        print("\n" + "="*50)
        print("SETUP COMPLETE!")
        print("  Username: admin")
        print("  Password: admin123")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed!\n")
        print(f"Error: {e}\n")
        print("Most common cause: Wrong MySQL credentials in .env file")
        print(f"Current DATABASE_URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
        sys.exit(1)
