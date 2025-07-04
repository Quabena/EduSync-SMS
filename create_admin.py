from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Creating admin user if it doesn't exist
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", email="admin@namongsdajhs.edu", role="admin")
        admin.set_password("admin_password")  # To be changed later in production
        db.session.add(admin)
        db.session.commit()
        print("Admin user created!")
    else:
        print("Admin already exists!")
