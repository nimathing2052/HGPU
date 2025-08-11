#!/usr/bin/env python3
"""
Hertie GPU Server Automation App - Startup Script
"""

import os
import sys
import subprocess
import time
from config import FLASK_PORT, FLASK_HOST, FLASK_DEBUG

def kill_existing_processes():
    """Kill any existing Flask processes"""
    try:
        # Kill any existing Python processes running our app
        subprocess.run(['pkill', '-f', 'python.*app.py'], check=False)
        subprocess.run(['pkill', '-f', 'python.*start_app.py'], check=False)
        
        # Kill any processes using our port
        subprocess.run(['lsof', '-ti', f':{FLASK_PORT}', '|', 'xargs', 'kill', '-9'], 
                      shell=True, check=False)
        
        print("🧹 Cleaned up existing processes")
        time.sleep(1)  # Give processes time to terminate
    except Exception as e:
        print(f"⚠️ Warning: Could not kill existing processes: {e}")

def find_available_port():
    """Find an available port for the browser to open"""
    try:
        # Check if our configured port is available
        result = subprocess.run(['lsof', '-i', f':{FLASK_PORT}'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            return FLASK_PORT
        
        # If port is in use, find next available port
        for port in range(FLASK_PORT + 1, FLASK_PORT + 100):
            result = subprocess.run(['lsof', '-i', f':{port}'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return port
        
        return FLASK_PORT  # Fallback
    except Exception:
        return FLASK_PORT

def main():
    """Main startup function"""
    print("🚀 Starting Hertie GPU Server Automation App...")
    print("=" * 50)
    
    # Kill any existing processes
    kill_existing_processes()
    
    # Find available port
    port = find_available_port()
    print(f"✅ Using port: {port}")
    print(f"🌐 Application will be available at: http://localhost:{port}")
    
    # Start the Flask application
    try:
        print("🚀 Starting Flask application...")
        os.environ['FLASK_PORT'] = str(port)
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
