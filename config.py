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
    
    # Mail settings
    MAIL_SERVER         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL        = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME       = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD       = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
    
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        logging.warning("MAIL_USERNAME or MAIL_PASSWORD is not set in the environment. Email sending may fail.")
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
