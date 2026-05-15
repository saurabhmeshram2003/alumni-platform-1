import os
import logging
from flask import Flask
from config import Config
from extensions import mail
from utils.otp import send_otp_email
import threading

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object(Config)
mail.init_app(app)

with app.app_context():
    print("Sending OTP via send_otp_email...")
    result = send_otp_email("academicsmaterial7474@gmail.com", "123456", "Test User")
    print(f"send_otp_email returned: {result}")
    
    # Wait for all daemon threads to finish
    for t in threading.enumerate():
        if t is not threading.current_thread():
            t.join(timeout=10)
    print("Done waiting.")
