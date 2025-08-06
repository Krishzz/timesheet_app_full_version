from app import create_app
from extensions import db
from models import User

app = create_app()

def create_users():
    with app.app_context():
        # Drop all old tables first (WARNING: deletes data)
        db.drop_all()
        db.create_all()

        if User.query.first():
            print("Users already exist, skipping creation.")
            return

        users = [
            {'username': 'employee@dewsoftware.com', 'password': 'employee@dew25', 'role': 'employee'},
            {'username': 'manager@dewsoftware.com', 'password': 'manager@dew26', 'role': 'manager'},
            {'username': 'admin@dewsoftware.com', 'password': 'admin@dew27', 'role': 'admin'},
        ]

        for u in users:
            user = User(username=u['username'], email=u['username'], role=u['role'])
            user.set_password(u['password'])
            db.session.add(user)

        db.session.commit()
        print("Users created successfully.")

if __name__ == '__main__':
    create_users()
