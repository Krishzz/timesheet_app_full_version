from flask import Flask
from config import Config
from extensions import db, login_manager
from routes.auth_routes import auth_bp
from routes.employee_routes import employee_bp
from routes.manager_routes import manager_bp
from routes.admin_routes import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(employee_bp, url_prefix='/employee')
    app.register_blueprint(manager_bp, url_prefix='/manager')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run()
