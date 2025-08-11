#!/bin/bash

# Hertie GPU Server Automation App Startup Script

echo "🚀 Starting Hertie GPU Server Automation App..."
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    echo "📦 Please install Python 3.8 or higher"
    exit 1
fi

# Check if virtual environment exists
if [ -d ".venv" ]; then
    echo "🔧 Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if requirements are installed
echo "📦 Checking dependencies..."
if ! python3 -c "import flask, paramiko" 2>/dev/null; then
    echo "⚠️  Dependencies not found. Installing..."
    pip install -r requirements.txt
fi

# Start the application
echo "🌐 Starting Flask application..."
python3 run.py
