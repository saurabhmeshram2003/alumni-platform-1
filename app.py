from flask import Flask, request, redirect, url_for, render_template_string, abort
from config import Config
from extensions import mongo, login_manager, mail
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    mongo.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    
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

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(alumni_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(mentorship_bp)
    app.register_blueprint(admin_bp)

    # ── REGISTRATION-ONLY MODE GATE ──────────────────────────────
    # Set REGISTRATION_ONLY=1 in .env to restrict access to auth routes only.
    # All other routes return 403.  Does NOT delete any logic.
    REGISTRATION_ONLY = os.getenv('REGISTRATION_ONLY', '0').strip() == '1'

    # Allowed URL prefixes/endpoints when mode is active
    _ALLOWED_ENDPOINTS = {
        'main.index',
        'auth.login',
        'auth.register',
        'auth.verify_otp',
        'auth.resend_otp',
        'auth.logout',
        'static',           # CSS / JS / images must still load
    }

    _RESTRICTED_403 = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Access Restricted – Alumni Registration Portal</title>
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-indigo-800
                 flex items-center justify-center font-sans">
      <div class="bg-white/10 backdrop-blur-md rounded-2xl p-10 text-center text-white
                  shadow-2xl max-w-md mx-4 border border-white/20">
        <div class="text-6xl mb-4">🔒</div>
        <h1 class="text-3xl font-extrabold mb-2">Access Restricted</h1>
        <p class="text-indigo-200 mb-6 text-sm">
          This portal is currently open for <strong>registration only</strong>.
          Please register or log in to continue.
        </p>
        <div class="flex gap-3 justify-center flex-wrap">
          <a href="/register"
             class="bg-indigo-500 hover:bg-indigo-400 text-white font-bold py-2 px-6
                    rounded-full transition-all shadow-lg">
            Register Now
          </a>
          <a href="/login"
             class="border border-white/40 hover:bg-white/10 text-white font-bold py-2 px-6
                    rounded-full transition-all">
            Log In
          </a>
        </div>
      </div>
    </body>
    </html>
    '''

    @app.before_request
    def registration_only_gate():
        if not REGISTRATION_ONLY:
            return  # Full access – do nothing
        endpoint = request.endpoint or ''
        # Allow any endpoint that starts with an allowed name
        if any(endpoint == ep or endpoint.startswith('static') for ep in _ALLOWED_ENDPOINTS):
            return
        # Block everything else with a friendly 403 page
        return _RESTRICTED_403, 403

    @app.after_request
    def after_request(response):
        """Allow framing in debug mode to fix VSCode preview issue"""
        if app.debug:
            response.headers['X-Frame-Options'] = '*'
        return response
    with app.app_context():
        # Ensure default admin exists
        # Use env vars; fall back to legacy defaults only if not set
        admin_email    = os.getenv('ADMIN_EMAIL', 'admin@123')
        admin_password = os.getenv('ADMIN_PASSWORD', 'Saurabh@123')
        admin_existing = mongo.db.users.find_one({'email': admin_email})
        
        if not admin_existing:
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

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
