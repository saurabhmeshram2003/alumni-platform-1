import os
import secrets
import logging

# Load .env for local development — on Railway/Render real env vars override this
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(16))
    MONGO_URI = os.environ.get('MONGO_URI')  # Must be set via Railway env vars
    
    # Security settings
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') != 'development'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Mail settings — all values come from Railway environment variables
    MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL        = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
    # Enable MAIL_DEBUG so Flask-Mail logs the full SMTP conversation in Railway
    MAIL_DEBUG          = True

    # ── Startup diagnostic print (visible in Railway logs) ───────────────────
    _mail_user = os.environ.get('MAIL_USERNAME')
    _mail_pass = os.environ.get('MAIL_PASSWORD')
    print(f"[CONFIG LOAD] MAIL_SERVER={os.environ.get('MAIL_SERVER', 'smtp.gmail.com')} "
          f"PORT={os.environ.get('MAIL_PORT', 587)} "
          f"TLS={os.environ.get('MAIL_USE_TLS', 'True')}")
    print(f"[CONFIG LOAD] MAIL_USERNAME={'SET (' + _mail_user + ')' if _mail_user else 'NOT SET *** CHECK RAILWAY ENV ***'}")
    print(f"[CONFIG LOAD] MAIL_PASSWORD={'SET (length=' + str(len(_mail_pass)) + ')' if _mail_pass else 'NOT SET *** CHECK RAILWAY ENV ***'}")
    print(f"[CONFIG LOAD] MAIL_DEFAULT_SENDER={os.environ.get('MAIL_DEFAULT_SENDER') or _mail_user}")

    if not _mail_user or not _mail_pass:
        logging.warning("MAIL_USERNAME or MAIL_PASSWORD is not set in the environment. Email sending will fail.")
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
