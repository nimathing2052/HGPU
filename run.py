#!/usr/bin/env python3
"""
Startup script for the Hertie GPU Server Automation Flask App
"""

import sys
import os
import subprocess

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['flask', 'paramiko']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install dependencies with:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True

def check_config():
    """Check if configuration file exists"""
    if not os.path.exists('config.py'):
        print("❌ config.py not found")
        print("📝 Creating default config.py...")
        
        # Create default config
        config_content = '''#!/usr/bin/env python3
"""
Configuration file for Hertie GPU Server Automation Flask App
"""

# Server Configuration
SERVER_HOST = "10.1.23.20"
SERVER_PORT = 22

# Local Port Configuration
LOCAL_PORT_RANGE = range(9000, 9100)

# Flask App Configuration
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 2344
FLASK_DEBUG = False

# Dynamic port range for Flask app
DYNAMIC_PORT_RANGE = range(2344, 2400)

# Session timeout (in seconds)
SESSION_TIMEOUT = 3600

# Jupyter Configuration
DEFAULT_JUPYTER_PORT = 9090
JUPYTER_STARTUP_TIMEOUT = 30

# SSH Configuration
SSH_TIMEOUT = 10
SSH_KEEPALIVE_INTERVAL = 60

# Container Management
CONTAINER_STARTUP_DELAY = 3
'''
        
        with open('config.py', 'w') as f:
            f.write(config_content)
        
        print("✅ Created default config.py")
    
    return True

def main():
    """Main startup function"""
    print("🚀 Starting Hertie GPU Server Automation App...\n")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check configuration
    if not check_config():
        sys.exit(1)
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("❌ app.py not found")
        print("📁 Please ensure all project files are present")
        sys.exit(1)
    
    print("✅ All checks passed")
    print("🌐 Starting Flask application...\n")
    
    try:
        # Import and run the Flask app
        from app import app
        
        # Get port from environment (Railway) or config
        port = int(os.getenv('PORT', 2344))
        
        print(f"📡 Server will be available at: http://localhost:{port}")
        print("🛑 Press Ctrl+C to stop the server\n")
        
        # Run the Flask app
        app.run(debug=False, host='0.0.0.0', port=port)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
