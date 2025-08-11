
#!/usr/bin/env python3
"""
Hertie GPU Server Automation Flask App
A minimal web application to automate GPU server access and Jupyter notebook setup.
"""

import os
import subprocess
import threading
import time
import sys
import signal
import atexit
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
import re

# Import the modular GPU Server Manager
from gpu_manager import GPUServerManager
# Import port utilities
from port_utils import find_available_local_port, find_available_flask_port, cleanup_all_ports
# Import session manager
from session_manager import session_manager

# Import configuration first
try:
    from config import SERVER_HOST, SERVER_PORT, LOCAL_PORT_RANGE, FLASK_HOST, FLASK_PORT, FLASK_DEBUG, SECRET_KEY
except ImportError:
    # Fallback configuration if config.py is not available
    SERVER_HOST = "10.1.23.20"
    SERVER_PORT = 22
    LOCAL_PORT_RANGE = range(9000, 9100)
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 2344
    FLASK_DEBUG = False
    SECRET_KEY = 'your-secret-key-change-in-production'

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Store active sessions (in production, use Redis or similar)




def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\n🛑 Received signal {signum}, cleaning up...")
    
    # Run port cleanup in parallel with session cleanup
    port_cleanup_thread = threading.Thread(
        target=cleanup_all_ports,
        args=(LOCAL_PORT_RANGE,),
        daemon=True
    )
    port_cleanup_thread.start()
    
    # Clean up all active sessions (now optimized with parallel processing)
    session_manager.shutdown()
    
    # Wait for port cleanup to complete (with timeout)
    port_cleanup_thread.join(timeout=10)
    
    print(f"✅ Cleanup completed, exiting...")
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function to run on exit
atexit.register(lambda: cleanup_all_ports(LOCAL_PORT_RANGE))

def strip_ansi_codes(text):
    """
    Remove ANSI escape sequences from text.
    
    Args:
        text (str): Text containing ANSI escape sequences
        
    Returns:
        str: Clean text without ANSI codes
    """
    # ANSI escape sequence pattern
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    return ansi_pattern.sub('', text)

@app.route('/')
def index():
    """Main page with authentication form and health check"""
    # Check if this is a health check request (Railway sends specific headers)
    user_agent = request.headers.get('User-Agent', '')
    if 'Railway' in user_agent or 'healthcheck' in user_agent.lower():
        return jsonify({
            'status': 'ok',
            'message': 'Hertie GPU Server Automation App is running',
            'timestamp': datetime.now().isoformat()
        })
    return render_template('index.html')

@app.route('/containers')
def containers():
    """Container management page"""
    return render_template('containers.html')

@app.route('/shell')
def shell():
    """Interactive shell page"""
    return render_template('shell.html')

@app.route('/health')
def health_check():
    """Health check endpoint for Railway monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'session_count': session_manager.get_session_count()
    })

@app.route('/api/status')
def api_status():
    """Simple API status endpoint for health checks"""
    return jsonify({
        'status': 'ok',
        'message': 'Hertie GPU Server Automation App is running',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint for health checks"""
    return "pong"

@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Handle initial authentication and get container list"""
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        
        print(f"🔐 Authentication attempt for: {email}")
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'})
        
        # Initialize GPU server manager
        manager = GPUServerManager(email, password, SERVER_HOST, SERVER_PORT)
        
        # Step 1: Connect to SSH
        print(f"🔗 Attempting SSH connection to {SERVER_HOST}...")
        success, message = manager.connect_ssh()
        print(f"SSH connection result: {success} - {message}")
        
        if not success:
            return jsonify({'success': False, 'message': message})
        
        # Step 2: Get container list
        print("📋 Getting container list...")
        success, output = manager.execute_command("/opt/aime-ml-containers/mlc-list")
        print(f"Container list result: {success}")
        print(f"Container list output: {output[:200]}...")  # First 200 chars
        
        if not success:
            manager.cleanup()
            return jsonify({'success': False, 'message': f'Failed to get container list: {output}'})
        
        # Parse container list using regex
        containers = parse_container_list(output)
        print(f"Parsed {len(containers)} containers")
        
        # Store manager in session for later use
        session_id = f"auth_{email}_{int(time.time())}"
        session_manager.create_session(session_id, manager, email)
        
        print(f"✅ Authentication successful for {email}")
        return jsonify({
            'success': True,
            'message': 'Authentication successful',
            'session_id': session_id,
            'containers': containers
        })
        
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Authentication error: {str(e)}'})

@app.route('/get-containers')
def get_containers():
    """Get container list for authenticated session"""
    session_id = request.args.get('session_id')
    
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    manager = session['manager']
    
    success, output = manager.execute_command("/opt/aime-ml-containers/mlc-list")
    if not success:
        return jsonify({'success': False, 'message': f'Failed to get container list: {output}'})
    
    containers = parse_container_list(output)
    return jsonify({'success': True, 'containers': containers})

@app.route('/create-container', methods=['POST'])
def create_container():
    """Create a new container"""
    session_id = request.form.get('session_id')
    container_name = request.form.get('container_name')
    framework = request.form.get('framework')
    version = request.form.get('version')
    
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    if not all([container_name, framework, version]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    manager = session['manager']
    
    # Check if container already exists
    exists, _ = manager.check_container_exists(container_name)
    if exists:
        return jsonify({'success': False, 'message': f'Container "{container_name}" already exists'})
    
    # Create container
    success, message = manager.create_container(container_name, framework, version)
    if not success:
        return jsonify({'success': False, 'message': f'Container creation failed: {message}'})
    
    return jsonify({'success': True, 'message': 'Container created successfully'})

@app.route('/start-container', methods=['POST'])
def start_container():
    """Start a container"""
    data = request.get_json()
    session_id = data.get('session_id')
    container_name = data.get('container_name')
    
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    manager = session['manager']
    
    success, message = manager.execute_command(f"/opt/aime-ml-containers/mlc-start {container_name}")
    if not success:
        return jsonify({'success': False, 'message': f'Failed to start container: {message}'})
    
    return jsonify({'success': True, 'message': 'Container started successfully'})

@app.route('/remove-container', methods=['POST'])
def remove_container():
    """Remove a container"""
    data = request.get_json()
    session_id = data.get('session_id')
    container_name = data.get('container_name')
    
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    manager = session['manager']
    
    # First stop the container if it's running
    print(f"🛑 Stopping container {container_name} before removal...")
    stop_success, stop_message = manager.execute_command(f"/opt/aime-ml-containers/mlc-stop {container_name} -Y")
    if not stop_success:
        print(f"⚠️ Warning: Failed to stop container: {stop_message}")
        # Continue anyway, maybe it's already stopped
    
    # Wait a moment for the stop to take effect
    time.sleep(2)
    
    # Now remove the container with interactive confirmation
    print(f"🗑️ Removing container {container_name}...")
    success, message = manager.execute_command(f"/opt/aime-ml-containers/mlc-remove {container_name}", interactive_input="Y")
    if not success:
        return jsonify({'success': False, 'message': f'Failed to remove container: {message}'})
    
    return jsonify({'success': True, 'message': 'Container removed successfully'})

@app.route('/launch-jupyter', methods=['POST'])
def launch_jupyter():
    """Launch Jupyter in a container"""
    data = request.get_json()
    session_id = data.get('session_id')
    container_name = data.get('container_name')
    
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    if not container_name:
        return jsonify({'success': False, 'message': 'Container name is required'})
    
    manager = session['manager']
    
    # Find available local port
    print(f"🔍 Looking for available local port...")
    local_port = find_available_local_port(LOCAL_PORT_RANGE)
    if not local_port:
        print(f"❌ No available local ports found")
        return jsonify({'success': False, 'message': 'No available local ports for forwarding'})
    
    print(f"✅ Found available local port: {local_port}")
    
    # Find optimal GPU based on availability
    print(f"🎯 Selecting optimal GPU based on availability...")
    optimal_gpu = manager.find_least_loaded_gpu()
    print(f"✅ Selected GPU {optimal_gpu} based on lowest utilization")
    
    # Start Jupyter in container with proper workflow
    print(f"🚀 Launching Jupyter for container: {container_name}")
    success, message, token, meta = manager.start_jupyter(container_name, 0)
    if not success:
        return jsonify({'success': False, 'message': f'Failed to start Jupyter: {message}'})

    actual_port = meta['port']; container_ip = meta['ip']
    success, msg = manager.setup_port_forwarding(container_ip, actual_port, local_port)
    if not success:
        return jsonify({'success': False, 'message': f'Port forwarding failed: {msg}'})
    
    jupyter_url = f"http://localhost:{local_port}"
    
    print(f"✅ Jupyter successfully launched at: {jupyter_url}")
    
    # Update session info with actual port and container IP
    session['jupyter_port'] = actual_port
    session['container_ip'] = container_ip
    session['local_port'] = local_port
    
    return jsonify({
        'success': True,
        'message': 'Jupyter launched successfully',
        'jupyter_url': jupyter_url,
        'local_port': local_port,
        'container_name': container_name,
        'token': token,  # Will be None if auth disabled
        'selected_gpu': optimal_gpu  # Add the selected GPU information
    })

def parse_container_list(mlc_output):
    """Parse the output of mlc-list command"""
    containers = []
    
    # Split output into lines and process each line
    lines = mlc_output.strip().split('\n')
    
    # Skip header lines
    for line in lines:
        line = line.strip()
        if not line or 'Available ml-containers are:' in line or 'CONTAINER' in line:
            continue
            
        # Parse container line using regex
        # Expected format: [container_name] Framework-version Status
        import re
        pattern = r'\[([^\]]+)\]\s+([^-]+)-([^\s]+)\s+(.+)'
        match = re.match(pattern, line)
        
        if match:
            container_name = match.group(1)
            framework = match.group(2).strip()
            version = match.group(3).strip()
            status = match.group(4).strip()
            
            containers.append({
                'name': container_name,
                'framework': framework,
                'version': version,
                'status': status
            })
    
    return containers

@app.route('/setup', methods=['POST'])
def setup_gpu_session():
    """Handle GPU session setup"""
    try:
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        container_name = request.form.get('container_name')
        framework = request.form.get('framework')
        version = request.form.get('version')
        
        # Validate inputs
        if not all([email, password, container_name, framework, version]):
            return jsonify({'success': False, 'message': 'All fields are required'})
        
        # Create session ID
        session_id = f"{email}_{container_name}_{int(time.time())}"
        
        # Initialize GPU server manager
        manager = GPUServerManager(email, password, SERVER_HOST, SERVER_PORT)
        
        # Step 1: Connect to SSH
        success, message = manager.connect_ssh()
        if not success:
            return jsonify({'success': False, 'message': message})
        
        # Step 2: Check if container exists, create if not
        exists, _ = manager.check_container_exists(container_name)
        if not exists:
            success, message = manager.create_container(container_name, framework, version)
            if not success:
                manager.cleanup()
                return jsonify({'success': False, 'message': f'Container creation failed: {message}'})
        
        # Step 3: Open container
        success, message = manager.open_container(container_name)
        if not success:
            manager.cleanup()
            return jsonify({'success': False, 'message': f'Container opening failed: {message}'})
        
        # Step 4: Start Jupyter
        success, message, token, meta = manager.start_jupyter(container_name, 0)
        if not success:
            manager.cleanup()
            return jsonify({'success': False, 'message': f'Jupyter startup failed: {message}'})
        
        # Step 5: Setup port forwarding
        local_port = find_available_local_port(LOCAL_PORT_RANGE)
        if not local_port:
            manager.cleanup()
            return jsonify({'success': False, 'message': 'No available local ports for forwarding'})
        
        actual_port = meta['port']; container_ip = meta['ip']
        success, message = manager.setup_port_forwarding(container_ip, actual_port, local_port)
        if not success:
            manager.cleanup()
            return jsonify({'success': False, 'message': f'Port forwarding failed: {message}'})
        
        # Store session info
        active_sessions[session_id] = {
            'manager': manager,
            'container_name': container_name,
            'jupyter_port': actual_port,
            'container_ip': container_ip,
            'local_port': local_port,
            'email': email,
            'created_at': time.time()
        }
        
        jupyter_url = f"http://localhost:{local_port}"
        
        return jsonify({
            'success': True,
            'message': 'GPU session setup completed successfully!',
            'session_id': session_id,
            'jupyter_url': jupyter_url,
            'container_name': container_name,
            'local_port': local_port
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'})

@app.route('/stop/<session_id>')
def stop_session(session_id):
    """Stop a GPU session"""
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'})
    
    try:
        manager = session['manager']
        
        # Stop the container
        manager.execute_command(f"/opt/aime-ml-containers/mlc-stop {session['container_name']} -Y")
        
        # Cleanup SSH connection and tunnel
        manager.cleanup()
        
        # Remove from active sessions
        session_manager.remove_session(session_id)
        
        return jsonify({'success': True, 'message': 'Session stopped successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error stopping session: {str(e)}'})

@app.route('/status')
def status():
    """Get status of all active sessions"""
    sessions_info = []
    active_sessions = session_manager.get_active_sessions()
    for session_id, session in active_sessions.items():
        sessions_info.append({
            'session_id': session_id,
            'container_name': session.get('container_name', 'N/A'),
            'jupyter_url': f"http://localhost:{session.get('local_port', 'N/A')}",
            'email': session['email'],
            'created_at': session['created_at']
        })
    
    return jsonify({'sessions': sessions_info})

@app.route('/logout', methods=['POST'])
def logout():
    """Logout and clean up session"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    print(f"🚪 Logout request for session: {session_id}")
    
    session = session_manager.get_session(session_id)
    if session:
        try:
            # Clean up the session
            manager = session['manager']
            
            # Clean up SSH connection and any tunnels
            manager.cleanup()
            
            # Remove from active sessions
            session_manager.remove_session(session_id)
            
            print(f"✅ Session {session_id} cleaned up successfully")
            return jsonify({'success': True, 'message': 'Logged out successfully'})
        except Exception as e:
            print(f"❌ Error during logout: {str(e)}")
            return jsonify({'success': False, 'message': f'Error during logout: {str(e)}'})
    else:
        print(f"⚠️ Session {session_id} not found or already logged out")
        return jsonify({'success': True, 'message': 'Session already ended'})

@app.route('/get-jupyter-token', methods=['POST'])
def get_jupyter_token():
    """Get Jupyter token for a running container"""
    data = request.get_json()
    session_id = data.get('session_id')
    container_name = data.get('container_name')
    
    print(f"🔑 Get Jupyter token request - Session: {session_id}, Container: {container_name}")
    print(f"🔍 Active sessions: {list(active_sessions.keys())}")
    
    session = session_manager.get_session(session_id)
    if not session:
        print(f"❌ Invalid session: {session_id}")
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    if not container_name:
        print(f"❌ No container name provided")
        return jsonify({'success': False, 'message': 'Container name is required'})
    
    manager = session['manager']
    
    print(f"🔍 Getting token for container: {container_name}")
    success, message, token = manager.get_jupyter_token(container_name)
    
    if not success:
        print(f"❌ Failed to get token: {message}")
        return jsonify({'success': False, 'message': message})
    
    print(f"✅ Token retrieved successfully: {token if token else 'No token (auth disabled)'}")
    return jsonify({
        'success': True,
        'message': message,
        'token': token
    })

@app.route('/gpu-info')
def gpu_info():
    """Get GPU usage information (requires active session)"""
    try:
        # For now, return a simple response to test the route
        return jsonify({'success': True, 'message': 'GPU info route is working', 'gpu_info': 'Test data'})
    except Exception as e:
        print(f"❌ Error in gpu_info route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error getting GPU info: {str(e)}'})

@app.route('/cleanup-ports', methods=['POST'])
def cleanup_ports():
    """Clean up only ports and SSH tunnels, keep sessions active"""
    try:
        print(f"🧹 Manual port cleanup requested...")
        
        # Get session ID from request
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        session = session_manager.get_session(session_id)
        if session:
            # Clean up only the SSH tunnel for this session, keep the session
            manager = session['manager']
            
            # Clean up only the tunnel, not the entire session
            if manager.local_port:
                try:
                    print(f"🧹 Cleaning up local port {manager.local_port}...")
                    cleanup_cmd = f"lsof -ti:{manager.local_port} | xargs kill -9 2>/dev/null || true"
                    subprocess.run(cleanup_cmd, shell=True, capture_output=True)
                    print(f"✅ Local port {manager.local_port} cleaned up")
                    
                    # Reset the local port
                    manager.local_port = None
                    manager.ssh_tunnel_process = None
                    
                except Exception as e:
                    print(f"⚠️ Error cleaning up local port {manager.local_port}: {e}")
        
        # Also run global port cleanup for any orphaned processes
        cleanup_all_ports(LOCAL_PORT_RANGE)
        
        return jsonify({
            'success': True, 
            'message': 'Ports and SSH tunnels cleaned up successfully (sessions preserved)'
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error during cleanup: {str(e)}'
        })

@app.route('/check-ports')
def check_ports():
    """Check which ports are currently in use"""
    try:
        port_range = LOCAL_PORT_RANGE
        used_ports = []
        
        for port in port_range:
            check_cmd = f"lsof -i:{port} 2>/dev/null"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                used_ports.append({
                    'port': port,
                    'processes': result.stdout.strip()
                })
        
        return jsonify({
            'success': True,
            'used_ports': used_ports,
            'total_checked': len(port_range)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error checking ports: {str(e)}'
        })

# WebSocket event handlers for interactive shell
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print(f"🔌 WebSocket client connected: {request.sid}")
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f"🔌 WebSocket client disconnected: {request.sid}")

@socketio.on('start_shell')
def handle_start_shell(data):
    """Start an interactive shell session"""
    try:
        session_id = data.get('session_id')
        container_name = data.get('container_name')  # Optional
        
        if not session_id:
            emit('shell_error', {'message': 'Session ID is required'})
            return
        
        session = session_manager.get_session(session_id)
        if not session:
            emit('shell_error', {'message': 'Invalid session'})
            return
        
        manager = session['manager']
        
        # Create interactive shell
        try:
            channel = manager.create_interactive_shell(container_name)
            
            # Store the channel in the session for later use
            session['shell_channel'] = channel
            session['shell_sid'] = request.sid
            
            print(f"🐚 Interactive shell started for session {session_id}")
            emit('shell_started', {'message': 'Interactive shell started'})
            
            # Store the socket ID for the background thread
            socket_id = request.sid
            
            # Start a thread to read from the channel and send to client
            def read_channel():
                try:
                    while True:
                        if channel.recv_ready():
                            data = channel.recv(1024).decode('utf-8', errors='ignore')
                            # Strip ANSI color codes from the output
                            clean_data = strip_ansi_codes(data)
                            socketio.emit('shell_output', {'data': clean_data}, room=socket_id)
                        time.sleep(0.1)
                except Exception as e:
                    print(f"❌ Shell read error: {e}")
                    socketio.emit('shell_error', {'message': f'Shell read error: {e}'}, room=socket_id)
            
            thread = threading.Thread(target=read_channel, daemon=True)
            thread.start()
            
        except Exception as e:
            emit('shell_error', {'message': f'Failed to start shell: {e}'})
            
    except Exception as e:
        emit('shell_error', {'message': f'Shell error: {e}'})

@socketio.on('shell_input')
def handle_shell_input(data):
    """Handle shell input from client"""
    try:
        session_id = data.get('session_id')
        command = data.get('command', '')
        
        if not session_id:
            emit('shell_error', {'message': 'Session ID is required'})
            return
        
        session = session_manager.get_session(session_id)
        if not session or 'shell_channel' not in session:
            emit('shell_error', {'message': 'No active shell session'})
            return
        
        channel = session['shell_channel']
        
        # Send command to shell
        channel.send(command)
        print(f"📤 Sent command to shell: {repr(command)}")
        
    except Exception as e:
        emit('shell_error', {'message': f'Shell input error: {e}'})

@socketio.on('stop_shell')
def handle_stop_shell(data):
    """Stop the interactive shell session"""
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('shell_error', {'message': 'Session ID is required'})
            return
        
        session = session_manager.get_session(session_id)
        if not session:
            emit('shell_error', {'message': 'Invalid session'})
            return
        
        # Close the shell channel
        if 'shell_channel' in session:
            try:
                session['shell_channel'].close()
                del session['shell_channel']
                del session['shell_sid']
                print(f"🐚 Shell session closed for {session_id}")
                emit('shell_stopped', {'message': 'Shell session closed'})
            except Exception as e:
                emit('shell_error', {'message': f'Error closing shell: {e}'})
        
    except Exception as e:
        emit('shell_error', {'message': f'Shell stop error: {e}'})

if __name__ == '__main__':
    # Clean up any expired sessions on startup
    session_manager.cleanup_expired_sessions()
    
    # Try to use configured port first, fall back to dynamic port finding
    port = FLASK_PORT
    try:
        # Test if configured port is available
        result = subprocess.run(f"lsof -i:{port}", shell=True, capture_output=True)
        if result.returncode == 0:
            # Port is in use, find available port
            port = find_available_flask_port()
            if port:
                print(f"⚠️  Port {FLASK_PORT} is in use, using port {port} instead")
            else:
                print(f"❌ No available ports found in range {FLASK_PORT}-2399")
                sys.exit(1)
    except:
        pass
    
    print(f"🚀 Starting Flask app with WebSocket support on port {port}")
    print(f"🔧 Session timeout: 1 hour")
    print(f"🧹 Auto-cleanup: Enabled")
    socketio.run(app, debug=FLASK_DEBUG, host=FLASK_HOST, port=port)
