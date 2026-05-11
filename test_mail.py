import os
import logging
from flask import Flask
from config import Config
from extensions import mail
from utils.otp import send_otp_email
import time

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object(Config)
mail.init_app(app)

with app.app_context():
    print("Sending OTP via send_otp_email...")
    result = send_otp_email("opercent517@gmail.com", "123456", "Test User")
    print(f"send_otp_email returned: {result}")
    
    # Wait to allow background thread to execute
    time.sleep(5)
    print("Done waiting.")
