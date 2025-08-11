"""
Configuration settings for the Hertie GPU Server Automation App
Supports both local development and cloud deployment via environment variables.
"""

import os

# Server Configuration
SERVER_HOST = os.getenv('GPU_SERVER_HOST', "10.1.23.20")
SERVER_PORT = int(os.getenv('GPU_SERVER_PORT', "22"))

# Flask Configuration
FLASK_HOST = os.getenv('FLASK_HOST', "0.0.0.0")
FLASK_PORT = int(os.getenv('PORT', os.getenv('FLASK_PORT', "2344")))  # Railway uses PORT env var
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

# Port Configuration
LOCAL_PORT_RANGE = range(9000, 9100)  # Range for local port forwarding
DYNAMIC_PORT_RANGE = range(2344, 2400)  # Range for dynamic Flask port allocation

# Framework Versions
FRAMEWORK_VERSIONS = {
    'Tensorflow': ['2.11.0', '2.10.0', '2.9.2-jlab', '2.9.0', '2.8.0', '2.7.0', '2.6.1', '2.5.0', '2.4.1', '2.4.0', '2.3.1-nvidia', '1.15.4-nvidia'],
    'Pytorch': ['2.1.0-aime', '2.1.0', '2.0.1-aime', '2.0.1', '2.0.0', '1.14.0a-nvidia', '1.13.1-aime', '1.13.0a-nvidia', '1.12.1-aime'],
    'Mxnet': ['1.8.0-nvidia']
}

# Session Configuration
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', "3600"))  # 1 hour in seconds
MAX_SESSIONS_PER_USER = int(os.getenv('MAX_SESSIONS_PER_USER', "5"))

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Security Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
