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
import paramiko
import re

app = Flask(__name__)

# Import configuration
try:
    from config import SERVER_HOST, SERVER_PORT, LOCAL_PORT_RANGE, FLASK_HOST, FLASK_PORT, FLASK_DEBUG
except ImportError:
    # Fallback configuration if config.py is not available
    SERVER_HOST = "10.1.23.20"
    SERVER_PORT = 22
    LOCAL_PORT_RANGE = range(9000, 9100)
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 2344
    FLASK_DEBUG = False

# Store active sessions (in production, use Redis or similar)
active_sessions = {}

def cleanup_all_ports():
    """Clean up all SSH tunnels and processes on local ports"""
    print(f"🧹 Global port cleanup initiated...")
    
    try:
        # Kill all SSH processes that might be using our port range
        port_range = LOCAL_PORT_RANGE
        for port in port_range:
            cleanup_cmd = f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
            result = subprocess.run(cleanup_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                print(f"✅ Cleaned up port {port}")
        
        # Also kill any ssh processes that might be hanging
        ssh_cleanup = "pkill -f 'ssh.*-L.*localhost' 2>/dev/null || true"
        subprocess.run(ssh_cleanup, shell=True, capture_output=True)
        print(f"✅ Cleaned up SSH tunnel processes")
        
    except Exception as e:
        print(f"⚠️ Error during global port cleanup: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\n🛑 Received signal {signum}, cleaning up...")
    cleanup_all_ports()
    
    # Clean up all active sessions
    for session_id, session in list(active_sessions.items()):
        try:
            manager = session['manager']
            manager.cleanup()
        except Exception as e:
            print(f"⚠️ Error cleaning up session {session_id}: {e}")
    
    active_sessions.clear()
    print(f"✅ Cleanup completed, exiting...")
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function to run on exit
atexit.register(cleanup_all_ports)

def cleanup_expired_sessions():
    """Clean up expired sessions"""
    current_time = time.time()
    expired_sessions = []
    
    for session_id, session in active_sessions.items():
        # Check if session is older than 1 hour (3600 seconds)
        if current_time - session.get('created_at', 0) > 3600:
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        try:
            session = active_sessions[session_id]
            manager = session['manager']
            manager.cleanup()
            del active_sessions[session_id]
            print(f"🧹 Cleaned up expired session: {session_id}")
        except Exception as e:
            print(f"❌ Error cleaning up session {session_id}: {e}")
            # Remove anyway to prevent memory leaks
            if session_id in active_sessions:
                del active_sessions[session_id]

class GPUServerManager:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.ssh_client = None
        self.container_name = None
        self.jupyter_port = None
        self.local_port = None
        self.ssh_tunnel_process = None
        
    def connect_ssh(self):
        """Establish SSH connection to the GPU server"""
        try:
            print(f"🔗 Creating SSH client for {self.email} to {SERVER_HOST}:{SERVER_PORT}")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            print(f"🔐 Attempting SSH connection...")
            self.ssh_client.connect(
                SERVER_HOST, 
                port=SERVER_PORT,
                username=self.email,
                password=self.password,
                timeout=10
            )
            print(f"✅ SSH connection successful")
            return True, "SSH connection established successfully"
        except Exception as e:
            print(f"❌ SSH connection failed: {type(e).__name__}: {str(e)}")
            return False, f"SSH connection failed: {str(e)}"
    
    def execute_command(self, command):
        """Execute command on the remote server"""
        if not self.ssh_client:
            return False, "No SSH connection established"
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if error:
                return False, f"Command error: {error}"
            return True, output
        except Exception as e:
            return False, f"Command execution failed: {str(e)}"
    
    def check_container_exists(self, container_name):
        """Check if container exists"""
        success, output = self.execute_command("/opt/aime-ml-containers/mlc-list")
        if not success:
            return False, output
        
        return container_name in output, output
    
    def create_container(self, container_name, framework, version):
        """Create a new container"""
        command = f"/opt/aime-ml-containers/mlc-create {container_name} {framework} {version}"
        return self.execute_command(command)
    
    def open_container(self, container_name):
        """Open an existing container"""
        command = f"/opt/aime-ml-containers/mlc-open {container_name}"
        return self.execute_command(command)
    
    def get_gpu_usage(self):
        """Get GPU usage information"""
        return self.execute_command("nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits")
    
    def find_least_loaded_gpu(self):
        """Find the GPU with the lowest utilization"""
        success, output = self.get_gpu_usage()
        if not success:
            return 0  # Default to GPU 0 if we can't get info
        
        gpus = []
        for line in output.strip().split('\n'):
            if line.strip():
                parts = line.split(', ')
                if len(parts) >= 4:
                    try:
                        gpu_id = int(parts[0])
                        utilization = int(parts[1])
                        memory_used = int(parts[2])
                        memory_total = int(parts[3])
                        gpus.append({
                            'id': gpu_id,
                            'utilization': utilization,
                            'memory_used': memory_used,
                            'memory_total': memory_total
                        })
                    except (ValueError, IndexError):
                        continue
        
        if not gpus:
            return 0
        
        # Find GPU with lowest utilization and memory usage
        least_loaded = min(gpus, key=lambda x: (x['utilization'], x['memory_used']))
        return least_loaded['id']

    def start_jupyter(self, container_name, port):
        """Start JupyterLab in container using tmux; auth disabled"""
        try:
            print(f"🚀 Starting Jupyter in container: {container_name}")

            # Stop any running jupyter
            self.execute_command("pkill -f jupyter || true")
            time.sleep(1)

            # Ensure container is up
            self.execute_command(f"/opt/aime-ml-containers/mlc-start {container_name}")
            time.sleep(2)

            # Get container id
            ok, container_id = self.execute_command(
                f"docker ps --filter 'name={container_name}' --format '{{{{.ID}}}}'"
            )
            if not ok or not container_id.strip():
                return False, f"Could not find container ID for {container_name}", None
            container_id = container_id.strip()

            # pick GPU (best-effort)
            ok, gpu_output = self.execute_command(
                f"docker exec {container_id} bash -lc "
                f"'nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader,nounits | "
                f"sort -t, -k2 -n | head -1 | cut -d, -f1'"
            )
            gpu_id = gpu_output.strip() if ok and gpu_output.strip() else "0"

            venv = "nimaenv"
            # Write a startup script inside container via heredoc to avoid quoting hell
            start_script = rf"""#!/usr/bin/env bash
    set -e
    cd /workspace || (mkdir -p /workspace && cd /workspace)

    # venv
    [ -d {venv} ] || python3 -m venv {venv}
    . {venv}/bin/activate

    # env
    export HOME=/workspace
    export JUPYTER_RUNTIME_DIR=/workspace/.jupyter/runtime
    export JUPYTER_DATA_DIR=/workspace/.jupyter
    export JUPYTER_CONFIG_DIR=/workspace/.jupyter
    mkdir -p "$JUPYTER_RUNTIME_DIR"

    python -m pip install -U pip
    python -m pip install jupyterlab ipykernel

    export CUDA_VISIBLE_DEVICES={gpu_id}

    # Start JupyterLab with auth disabled
    exec jupyter lab \
    --no-browser \
    --ip=0.0.0.0 \
    --port={port} \
    --ServerApp.token='' \
    --ServerApp.password='' \
    --allow-root
    """
            # Drop the script and make it executable
            put_script_cmd = (
                f"docker exec {container_id} bash -lc "
                f"\"cat > /workspace/start_jlab.sh << 'EOF'\n{start_script}\nEOF\nchmod +x /workspace/start_jlab.sh\""
            )
            ok, out = self.execute_command(put_script_cmd)
            if not ok:
                return False, f"Failed to write startup script: {out}", None

            # Try tmux; fall back to background
            tmux_sess = re.sub(r'[^A-Za-z0-9_.-]', '-', f"jup-{container_name}-{port}")
            run_tmux_cmd = (
                f"docker exec {container_id} bash -lc "
                f"\"if command -v tmux >/dev/null 2>&1; then "
                f"tmux has-session -t {tmux_sess} 2>/dev/null && tmux kill-session -t {tmux_sess} || true; "
                f"tmux new-session -d -s {tmux_sess} '/workspace/start_jlab.sh'; "
                f"echo tmux_ok; "
                f"else echo tmux_missing; fi\""
            )
            ok, out = self.execute_command(run_tmux_cmd)
            if ok and "tmux_ok" in out:
                # Confirm it’s up
                time.sleep(2)
                return True, f"JupyterLab started on port {port} in tmux session {tmux_sess} (auth disabled)", None

            # Fallback: background process
            bg_cmd = (
                f"docker exec -d {container_id} bash -lc "
                f"\"/workspace/start_jlab.sh > /workspace/jupyter.log 2>&1\""
            )
            ok, out = self.execute_command(bg_cmd)
            if not ok:
                return False, f"Failed to start JupyterLab: {out}", None

            time.sleep(2)
            # Quick check
            ok, ps = self.execute_command(
                f"docker exec {container_id} bash -lc \"pgrep -fa 'jupyter.*lab' || true\""
            )
            if ok and ps.strip():
                return True, f"JupyterLab started on port {port} (auth disabled)", None
            return False, f"JupyterLab not found running: {ps}", None

        except Exception as e:
            return False, f"Error starting Jupyter: {e}", None

    
    def setup_port_forwarding(self, remote_port, local_port):
        """Set up SSH tunnel for port forwarding"""
        try:
            # Kill any existing tunnel on this port
            subprocess.run(f"lsof -ti:{local_port} | xargs kill -9", shell=True, capture_output=True)
            
            # Create SSH tunnel with password authentication
            # Using sshpass to provide password non-interactively
            tunnel_cmd = f"sshpass -p '{self.password}' ssh -f -N -L {local_port}:localhost:{remote_port} {self.email}@{SERVER_HOST}"
            print(f"🔗 Creating SSH tunnel: {tunnel_cmd}")
            
            # Execute the tunnel command
            result = subprocess.run(tunnel_cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                print(f"✅ SSH tunnel established successfully")
                print(f"result: {result.stdout}")
                return True, f"Port forwarding established: localhost:{local_port} -> server:{remote_port}, result: {result.stdout}"
            else:
                print(f"❌ SSH tunnel failed: {result.stderr}")
                return False, f"Failed to establish port forwarding: {result.stderr}"
                
        except Exception as e:
            print(f"❌ SSH tunnel exception: {str(e)}")
            return False, f"Port forwarding failed: {str(e)}"
    
    def cleanup(self):
        """Clean up SSH connection and tunnel"""
        print(f"🧹 Cleaning up SSH tunnel and connection...")
        
        # Clean up SSH tunnel process
        if self.ssh_tunnel_process:
            try:
                print(f"🛑 Terminating SSH tunnel process...")
                self.ssh_tunnel_process.terminate()
                self.ssh_tunnel_process.wait(timeout=5)
                print(f"✅ SSH tunnel process terminated")
            except:
                print(f"⚠️ Force killing SSH tunnel process...")
                self.ssh_tunnel_process.kill()
        
        # Clean up SSH client
        if self.ssh_client:
            try:
                print(f"🔌 Closing SSH connection...")
                self.ssh_client.close()
                print(f"✅ SSH connection closed")
            except Exception as e:
                print(f"⚠️ Error closing SSH connection: {e}")
        
        # Clean up any remaining SSH processes on local ports
        if self.local_port:
            try:
                print(f"🧹 Cleaning up local port {self.local_port}...")
                cleanup_cmd = f"lsof -ti:{self.local_port} | xargs kill -9 2>/dev/null || true"
                subprocess.run(cleanup_cmd, shell=True, capture_output=True)
                print(f"✅ Local port {self.local_port} cleaned up")
            except Exception as e:
                print(f"⚠️ Error cleaning up local port {self.local_port}: {e}")
    
    def stop_jupyter(self, container_name, port):
        """Stop JupyterLab session using tmux"""
        try:
            print(f"🛑 Stopping JupyterLab in container: {container_name}")
            
            # Get container ID
            container_id_cmd = f"docker ps --filter 'name={container_name}' --format '{{{{.ID}}}}'"
            success, container_id = self.execute_command(container_id_cmd)
            if not success or not container_id.strip():
                return False, f"Could not find container ID for {container_name}"
            
            container_id = container_id.strip()
            tmux_session = f"jup-{container_name}-{port}"
            
            # Kill tmux session
            stop_cmd = f"docker exec {container_id} bash -c 'tmux has-session -t {tmux_session} 2>/dev/null && tmux kill-session -t {tmux_session} && echo \"Session killed\" || echo \"Session not found\"'"
            success, output = self.execute_command(stop_cmd)
            
            if success and "Session killed" in output:
                print(f"✅ JupyterLab session stopped: {tmux_session}")
                return True, f"JupyterLab session stopped: {tmux_session}"
            else:
                print(f"⚠️ Session not found or already stopped: {tmux_session}")
                return True, f"JupyterLab session already stopped: {tmux_session}"
                
        except Exception as e:
            print(f"❌ Error stopping Jupyter: {str(e)}")
            return False, f"Error stopping Jupyter: {str(e)}"

    def get_jupyter_token(self, container_name):
        """Get JupyterLab status (authentication disabled - no token needed)"""
        try:
            print(f"🔍 DEBUG: Starting token extraction for container: {container_name}")
            
            # Get container ID
            container_id_cmd = f"docker ps --filter 'name={container_name}' --format '{{{{.ID}}}}'"
            success, container_id = self.execute_command(container_id_cmd)
            if not success or not container_id.strip():
                print(f"❌ DEBUG: Could not find container ID for {container_name}")
                return False, "Could not find container ID", None
            
            container_id = container_id.strip()
            print(f"🔍 DEBUG: Found container ID: {container_id}")
            
            # Check if JupyterLab is running via tmux sessions
            print(f"🔍 DEBUG: Checking JupyterLab tmux sessions...")
            
            # Look for tmux sessions for this container
            tmux_check_cmd = f"docker exec {container_id} bash -c 'tmux list-sessions 2>/dev/null | grep jup-{container_name}'"
            success, tmux_output = self.execute_command(tmux_check_cmd)
            print(f"🔍 DEBUG: Tmux sessions check - Success: {success}")
            print(f"🔍 DEBUG: Tmux sessions output: {repr(tmux_output)}")
            
            if success and tmux_output.strip():
                print(f"✅ DEBUG: JupyterLab tmux session found (authentication disabled)")
                return True, f"JupyterLab running in tmux session: {tmux_output.strip()} (authentication disabled)", None
            
            # Fallback: Check if JupyterLab is running via process
            print(f"🔍 DEBUG: Checking JupyterLab process...")
            simple_cmd = f"docker exec {container_id} jupyter lab list"
            success, simple_output = self.execute_command(simple_cmd)
            print(f"🔍 DEBUG: JupyterLab status - Success: {success}")
            print(f"🔍 DEBUG: JupyterLab output: {repr(simple_output)}")
            
            if success and simple_output:
                print(f"✅ DEBUG: JupyterLab is running (authentication disabled)")
                return True, "JupyterLab is running (authentication disabled - no token needed)", None
            
            # First, check if jupyter is available and install if needed
            print(f"🔍 DEBUG: Checking jupyter availability...")
            check_jupyter_cmd = f"docker exec {container_id} sh -lc 'cd /workspace && . nimaenv/bin/activate && export HOME=/workspace && which jupyter'"
            success, jupyter_path = self.execute_command(check_jupyter_cmd)
            print(f"🔍 DEBUG: Jupyter check result - Success: {success}, Path: {repr(jupyter_path)}")
            
            if not success or not jupyter_path.strip():
                print(f"⚠️ DEBUG: Jupyter not found, attempting to install...")
                # Try to install jupyter in the virtual environment with proper environment
                install_cmd = f"docker exec {container_id} sh -lc 'cd /workspace && . nimaenv/bin/activate && export HOME=/workspace && pip install --user jupyter jupyterlab'"
                success, install_output = self.execute_command(install_cmd)
                print(f"🔍 DEBUG: Installation result - Success: {success}, Output: {repr(install_output)}")
                
                if not success:
                    print(f"❌ DEBUG: Failed to install jupyter, trying alternative method...")
                    # Try alternative installation method
                    install_cmd2 = f"docker exec {container_id} sh -lc 'cd /workspace && . nimaenv/bin/activate && export HOME=/workspace && export PIP_CACHE_DIR=/workspace/.pip_cache && mkdir -p $PIP_CACHE_DIR && pip install jupyter jupyterlab'"
                    success, install_output = self.execute_command(install_cmd2)
                    print(f"🔍 DEBUG: Alternative installation result - Success: {success}, Output: {repr(install_output)}")
                    
                    if not success:
                        print(f"❌ DEBUG: Alternative installation also failed")
                        return False, f"Jupyter not available and installation failed: {install_output}", None
                    else:
                        print(f"✅ DEBUG: Jupyter installed successfully with alternative method")
                else:
                    print(f"✅ DEBUG: Jupyter installed successfully")
            
            # Now try to get the jupyter lab list with full environment
            print(f"🔍 DEBUG: Trying jupyter lab list with full environment...")
            list_cmd = f"docker exec {container_id} sh -lc 'cd /workspace && . nimaenv/bin/activate && export HOME=/workspace && export JUPYTER_RUNTIME_DIR=/workspace/.jupyter/runtime && export JUPYTER_DATA_DIR=/workspace/.jupyter && export JUPYTER_CONFIG_DIR=/workspace/.jupyter && jupyter lab list'"
            success, output = self.execute_command(list_cmd)
            print(f"🔍 DEBUG: Full environment command result - Success: {success}")
            print(f"🔍 DEBUG: Full environment output: {repr(output)}")
            
            if not success:
                print(f"❌ DEBUG: Jupyter list command failed, checking if jupyter is running...")
                # Try alternative approach - check if jupyter is running via ps
                ps_cmd = f"docker exec {container_id} bash -c 'ps aux | grep jupyter'"
                success, ps_output = self.execute_command(ps_cmd)
                print(f"🔍 DEBUG: PS command result - Success: {success}, Output: {repr(ps_output)}")
                
                if success and 'jupyter' in ps_output:
                    print(f"🔍 DEBUG: Jupyter is running but token extraction failed")
                    return True, "Jupyter is running but token extraction failed. Try launching Jupyter again.", None
                else:
                    print(f"❌ DEBUG: Jupyter not running")
                    return False, f"Jupyter not running. Please launch Jupyter first: {output}", None
            
            # Extract token from output with multiple patterns
            print(f"🔍 DEBUG: Attempting token extraction...")
            
            # Try multiple token patterns
            patterns = [
                r'token=([a-zA-Z0-9]{32,})',  # Standard pattern
                r'token=([a-z0-9]+)',         # Simple pattern (as suggested)
                r'token=([a-zA-Z0-9]+)',      # Alphanumeric pattern
            ]
            
            for i, pattern in enumerate(patterns):
                print(f"🔍 DEBUG: Trying pattern {i+1}: {pattern}")
                match = re.search(pattern, output)
                if match:
                    token = match.group(1)
                    print(f"🔑 DEBUG: Token found with pattern {i+1}: {token}")
                    return True, f"Token found: {token}", token
            
            print(f"✅ DEBUG: No token found with any pattern, authentication likely disabled")
            print(f"🔍 DEBUG: Full output for manual inspection: {repr(output)}")
            return True, "No token found (authentication disabled)", None
                
        except Exception as e:
            print(f"❌ DEBUG: Exception in get_jupyter_token: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Error getting Jupyter token: {str(e)}", None

def find_available_local_port():
    """Find an available local port for forwarding"""
    # Convert tuple to range if needed
    if isinstance(LOCAL_PORT_RANGE, tuple):
        port_range = range(LOCAL_PORT_RANGE[0], LOCAL_PORT_RANGE[1] + 1)
    else:
        port_range = LOCAL_PORT_RANGE
    
    print(f"🔍 Checking ports in range: {port_range}")
    
    for port in port_range:
        try:
            # Check if port is available
            result = subprocess.run(f"lsof -i:{port}", shell=True, capture_output=True)
            if result.returncode != 0:
                print(f"✅ Found available port: {port}")
                return port
            else:
                print(f"❌ Port {port} is in use")
        except Exception as e:
            print(f"⚠️ Error checking port {port}: {e}")
            continue
    
    print(f"❌ No available ports found in range {port_range}")
    return None

def find_available_flask_port():
    """Find an available port for Flask app"""
    try:
        from config import DYNAMIC_PORT_RANGE
        port_range = DYNAMIC_PORT_RANGE
    except ImportError:
        port_range = range(2344, 2400)
    
    for port in port_range:
        try:
            # Check if port is available
            result = subprocess.run(f"lsof -i:{port}", shell=True, capture_output=True)
            if result.returncode != 0:
                return port
        except:
            continue
    return None

@app.route('/')
def index():
    """Main page with authentication form"""
    return render_template('index.html')

@app.route('/containers')
def containers():
    """Container management page"""
    return render_template('containers.html')

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
        manager = GPUServerManager(email, password)
        
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
        active_sessions[session_id] = {
            'manager': manager,
            'email': email,
            'authenticated': True,
            'created_at': time.time()
        }
        
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
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    session = active_sessions[session_id]
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
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    if not all([container_name, framework, version]):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    session = active_sessions[session_id]
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
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    session = active_sessions[session_id]
    manager = session['manager']
    
    success, message = manager.execute_command(f"/opt/aime-ml-containers/mlc-start {container_name}")
    if not success:
        return jsonify({'success': False, 'message': f'Failed to start container: {message}'})
    
    return jsonify({'success': True, 'message': 'Container started successfully'})

@app.route('/stop-container', methods=['POST'])
def stop_container():
    """Stop a container"""
    data = request.get_json()
    session_id = data.get('session_id')
    container_name = data.get('container_name')
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    session = active_sessions[session_id]
    manager = session['manager']
    
    success, message = manager.execute_command(f"/opt/aime-ml-containers/mlc-stop {container_name} -Y")
    if not success:
        return jsonify({'success': False, 'message': f'Failed to stop container: {message}'})
    
    return jsonify({'success': True, 'message': 'Container stopped successfully'})

@app.route('/launch-jupyter', methods=['POST'])
def launch_jupyter():
    """Launch Jupyter in a container"""
    data = request.get_json()
    session_id = data.get('session_id')
    container_name = data.get('container_name')
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    if not container_name:
        return jsonify({'success': False, 'message': 'Container name is required'})
    
    session = active_sessions[session_id]
    manager = session['manager']
    
    # Find available local port
    print(f"🔍 Looking for available local port...")
    local_port = find_available_local_port()
    if not local_port:
        print(f"❌ No available local ports found")
        return jsonify({'success': False, 'message': 'No available local ports for forwarding'})
    
    print(f"✅ Found available local port: {local_port}")
    
    # Start Jupyter in container with proper workflow
    # Use port in range 9000-9099 as per documentation
    jupyter_port = 9090  # Default port
    print(f"🚀 Launching Jupyter for container: {container_name}")
    success, message, token = manager.start_jupyter(container_name, jupyter_port)
    if not success:
        return jsonify({'success': False, 'message': f'Failed to start Jupyter: {message}'})
    
    # Setup port forwarding
    print(f"🔗 Setting up port forwarding: localhost:{local_port} -> server:{jupyter_port}")
    success, message = manager.setup_port_forwarding(jupyter_port, local_port)
    if not success:
        return jsonify({'success': False, 'message': f'Port forwarding failed: {message}'})
    
    jupyter_url = f"http://localhost:{local_port}"
    
    print(f"✅ Jupyter successfully launched at: {jupyter_url}")
    
    return jsonify({
        'success': True,
        'message': 'Jupyter launched successfully',
        'jupyter_url': jupyter_url,
        'local_port': local_port,
        'container_name': container_name,
        'token': token  # Will be None if auth disabled
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
        jupyter_port = int(request.form.get('jupyter_port', 9090))
        
        # Validate inputs
        if not all([email, password, container_name, framework, version]):
            return jsonify({'success': False, 'message': 'All fields are required'})
        
        # Create session ID
        session_id = f"{email}_{container_name}_{int(time.time())}"
        
        # Initialize GPU server manager
        manager = GPUServerManager(email, password)
        
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
        success, message, token = manager.start_jupyter(container_name, jupyter_port)
        if not success:
            manager.cleanup()
            return jsonify({'success': False, 'message': f'Jupyter startup failed: {message}'})
        
        # Step 5: Setup port forwarding
        local_port = find_available_local_port()
        if not local_port:
            manager.cleanup()
            return jsonify({'success': False, 'message': 'No available local ports for forwarding'})
        
        success, message = manager.setup_port_forwarding(jupyter_port, local_port)
        if not success:
            manager.cleanup()
            return jsonify({'success': False, 'message': f'Port forwarding failed: {message}'})
        
        # Store session info
        active_sessions[session_id] = {
            'manager': manager,
            'container_name': container_name,
            'jupyter_port': jupyter_port,
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
    if session_id not in active_sessions:
        return jsonify({'success': False, 'message': 'Session not found'})
    
    try:
        session = active_sessions[session_id]
        manager = session['manager']
        
        # Stop the container
        manager.execute_command(f"/opt/aime-ml-containers/mlc-stop {session['container_name']} -Y")
        
        # Cleanup SSH connection and tunnel
        manager.cleanup()
        
        # Remove from active sessions
        del active_sessions[session_id]
        
        return jsonify({'success': True, 'message': 'Session stopped successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error stopping session: {str(e)}'})

@app.route('/status')
def status():
    """Get status of all active sessions"""
    sessions_info = []
    for session_id, session in active_sessions.items():
        sessions_info.append({
            'session_id': session_id,
            'container_name': session['container_name'],
            'jupyter_url': f"http://localhost:{session['local_port']}",
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
    
    if session_id and session_id in active_sessions:
        try:
            # Clean up the session
            session = active_sessions[session_id]
            manager = session['manager']
            
            # Clean up SSH connection and any tunnels
            manager.cleanup()
            
            # Remove from active sessions
            del active_sessions[session_id]
            
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
    
    if not session_id or session_id not in active_sessions:
        print(f"❌ Invalid session: {session_id}")
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    if not container_name:
        print(f"❌ No container name provided")
        return jsonify({'success': False, 'message': 'Container name is required'})
    
    session = active_sessions[session_id]
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
    if not active_sessions:
        return jsonify({'success': False, 'message': 'No active sessions'})
    
    # Use the first available session
    session = next(iter(active_sessions.values()))
    manager = session['manager']
    
    success, output = manager.get_gpu_usage()
    if success:
        return jsonify({'success': True, 'gpu_info': output})
    else:
        return jsonify({'success': False, 'message': output})

@app.route('/cleanup-ports', methods=['POST'])
def cleanup_ports():
    """Clean up only ports and SSH tunnels, keep sessions active"""
    try:
        print(f"🧹 Manual port cleanup requested...")
        
        # Get session ID from request
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if session_id and session_id in active_sessions:
            # Clean up only the SSH tunnel for this session, keep the session
            session = active_sessions[session_id]
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
        cleanup_all_ports()
        
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

@app.route('/full-cleanup', methods=['POST'])
def full_cleanup():
    """Clean up everything - ports, tunnels, and sessions"""
    try:
        print(f"🧹 Full cleanup requested...")
        
        # Clean up all active sessions
        for session_id, session in list(active_sessions.items()):
            try:
                manager = session['manager']
                manager.cleanup()
                print(f"✅ Cleaned up session {session_id}")
            except Exception as e:
                print(f"⚠️ Error cleaning up session {session_id}: {e}")
        
        # Clear all sessions
        active_sessions.clear()
        
        # Run global port cleanup
        cleanup_all_ports()
        
        return jsonify({
            'success': True, 
            'message': 'Full cleanup completed - all sessions and ports cleared'
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error during full cleanup: {str(e)}'
        })

if __name__ == '__main__':
    # Clean up any expired sessions on startup
    cleanup_expired_sessions()
    
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
    
    print(f"🚀 Starting Flask app on port {port}")
    print(f"🔧 Session timeout: 1 hour")
    print(f"🧹 Auto-cleanup: Enabled")
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=port)