import os
import secrets

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(16))
    MONGO_URI = os.environ.get('MONGO_URI')  # Must be set via Railway env vars
    
    # Mail settings
    MAIL_SERVER         = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL        = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME       = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD       = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER') or os.getenv('MAIL_USERNAME')
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
