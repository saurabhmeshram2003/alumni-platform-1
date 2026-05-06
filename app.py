from flask import Flask, request, redirect, url_for, render_template_string, abort
from config import Config
from extensions import mongo, login_manager, mail, limiter
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    try:
        if app.config.get('MONGO_URI'):
            mongo.init_app(app)
            if mongo.cx:
                mongo.cx.server_info()
                app.logger.info("MongoDB initialized and connected successfully.")
        else:
            app.logger.error("MONGO_URI is NOT set in environment. Skipping MongoDB initialization.")
    except Exception as e:
        app.logger.error(f"MongoDB connection failed on startup: {e}")

    login_manager.init_app(app)
    
    mail.init_app(app)
    limiter.init_app(app)
    app.logger.info("Mail initialized with USERNAME: %s", "SET" if app.config.get('MAIL_USERNAME') else "NOT SET")
    app.logger.info("App startup complete.")
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.alumni import alumni_bp
    from routes.jobs import jobs_bp
    from routes.events import events_bp
    from routes.mentorship import mentorship_bp
    from routes.admin import admin_bp
    from routes.stories import stories_bp
    from routes.notifications import notifications_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(alumni_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(mentorship_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(stories_bp)
    app.register_blueprint(notifications_bp)


    # Endpoints always accessible regardless of launch mode
    _PRE_LAUNCH_ALLOWED = {
        'main.index',
        'main.coming_soon',
        'auth.register',
        'auth.login',
        'auth.verify_otp',
        'auth.resend_otp',
        'static',
    }

    @app.before_request
    def launch_mode_gate():
        """Pre-launch guard — read env var per-request so Render changes apply instantly."""
        # Default to '1' (full access) — must explicitly set LAUNCH_MODE=0 to restrict
        launch_mode = os.getenv('LAUNCH_MODE', '1').strip() == '1'
        if launch_mode:
            return  # Platform is live — full access, no gate
        endpoint = request.endpoint or ''
        if any(endpoint == ep or endpoint.startswith('static') for ep in _PRE_LAUNCH_ALLOWED):
            return  # Allowed through pre-launch gate
        return redirect(url_for('main.coming_soon'))

    @app.after_request
    def after_request(response):
        """Allow framing in debug mode to fix VSCode preview issue"""
        if app.debug:
            response.headers['X-Frame-Options'] = '*'
        return response

    # ── Admin seeding (first-request, non-blocking) ──────────────────────────
    # NOTE: @app.before_first_request was removed in Flask 2.3.
    # We use a nonlocal flag instead — safe and equivalent.
    _admin_seeded = False

    @app.before_request
    def ensure_default_admin():
        """Seed the default admin user once on first request.
        Wrapped in try/except so a DB hiccup never crashes the app.
        """
        nonlocal _admin_seeded
        if _admin_seeded:
            return
        _admin_seeded = True
        try:
            admin_email    = os.getenv('ADMIN_EMAIL', 'admin@123')
            admin_password = os.getenv('ADMIN_PASSWORD', 'Saurabh@123')
            if not mongo.db.users.find_one({'email': admin_email}):
                from werkzeug.security import generate_password_hash
                from datetime import datetime
                mongo.db.users.insert_one({
                    'name': 'System Admin',
                    'email': admin_email,
                    'password': generate_password_hash(admin_password),
                    'role': 'admin',
                    'graduation_year': None,
                    'department': 'Administration',
                    'company': None,
                    'skills': [],
                    'linkedin': None,
                    'profile_image': 'default.png',
                    'created_at': datetime.utcnow(),
                    'is_approved': True,
                    'verified': True,
                })
                app.logger.info("[Admin seed] Default admin created.")
        except Exception as e:
            app.logger.error(f"[Admin seed] Failed to seed default admin: {e}")

    return app

# Expose app globally for gunicorn app:app
app = create_app()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
