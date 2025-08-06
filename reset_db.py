from app import create_app
from extensions import db
from sqlalchemy import text  # ✅ required import

app = create_app()

with app.app_context():
    inspector = db.inspect(db.engine)
    for table_name in inspector.get_table_names():
        drop_statement = text(f'DROP TABLE IF EXISTS {table_name} CASCADE;')
        db.session.execute(drop_statement)  # ✅ wrapped in text()
    db.session.commit()

    print("✅ All tables dropped with CASCADE.")

    db.create_all()
    print("✅ Tables recreated successfully.")
