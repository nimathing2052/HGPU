#!/usr/bin/env python3
"""
GPU Server Manager Module
Handles SSH connections, container operations, and GPU optimization for the Hertie GPU server.
"""

import os
import subprocess
import time
import json
import paramiko
import re
import base64

class GPUServerManager:
    """Manages SSH connections and container operations for the GPU server."""
    
    def __init__(self, email, password, server_host="10.1.23.20", server_port=22):
        """
        Initialize the GPU Server Manager.
        
        Args:
            email (str): User email for SSH authentication
            password (str): User password for SSH authentication
            server_host (str): GPU server hostname/IP
            server_port (int): SSH port number
        """
        self.email = email
        self.password = password
        self.server_host = server_host
        self.server_port = server_port
        self.ssh_client = None
        self.container_name = None
        self.jupyter_port = None
        self.local_port = None
        self.ssh_tunnel_process = None
        
    def connect_ssh(self):
        """Establish SSH connection to the GPU server."""
        try:
            print(f"🔗 Creating SSH client for {self.email} to {self.server_host}:{self.server_port}")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            print(f"🔐 Attempting SSH connection...")
            self.ssh_client.connect(
                self.server_host, 
                port=self.server_port,
                username=self.email,
                password=self.password,
                timeout=10
            )
            print(f"✅ SSH connection successful")
            return True, "SSH connection established successfully"
        except Exception as e:
            print(f"❌ SSH connection failed: {type(e).__name__}: {str(e)}")
            return False, f"SSH connection failed: {str(e)}"
    
    def _run(self, cmd: str, *, login_shell: bool = True, get_pty: bool = False, timeout: int = 60, interactive_input: str = None):
        """
        Execute command with proper shell handling and keepalive.
        
        Args:
            cmd (str): Command to execute
            login_shell (bool): Whether to use login shell
            get_pty (bool): Whether to allocate pseudo-terminal
            timeout (int): Command timeout in seconds (reduced default from 120 to 60)
            interactive_input (str): Input to send for interactive commands
            
        Returns:
            tuple: (success, output)
        """
        if not self.ssh_client:
            return False, "No SSH connection"
        
        # Set keepalive on transport
        t = self.ssh_client.get_transport()
        if t: 
            t.set_keepalive(15)  # Reduced from 30 to 15 seconds
        
        # Ensure PATH is loaded properly
        if login_shell:
            # Use login shell with proper quoting
            full = f"bash -lc {json.dumps(cmd)}"
        else:
            full = cmd
            
        # For interactive commands, we need a pseudo-terminal
        if interactive_input:
            get_pty = True
            
        stdin, stdout, stderr = self.ssh_client.exec_command(full, get_pty=get_pty, timeout=timeout)
        
        # Handle interactive input if provided
        if interactive_input and stdin:
            stdin.write(interactive_input + '\n')
            stdin.flush()
        
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        code = stdout.channel.recv_exit_status()
        if code != 0:
            return False, err or out
        return True, out

    def execute_command(self, command, interactive_input=None):
        """
        Execute command on the remote server.
        
        Args:
            command (str): Command to execute
            interactive_input (str): Input for interactive commands
            
        Returns:
            tuple: (success, output)
        """
        return self._run(command, login_shell=True, interactive_input=interactive_input)[0:2]
    
    def check_container_exists(self, container_name):
        """
        Check if container exists.
        
        Args:
            container_name (str): Name of the container to check
            
        Returns:
            tuple: (exists, output)
        """
        success, output = self.execute_command("/opt/aime-ml-containers/mlc-list")
        if not success:
            return False, output
        
        return container_name in output, output
    
    def create_container(self, container_name, framework, version):
        """
        Create a new container.
        
        Args:
            container_name (str): Name for the new container
            framework (str): ML framework (Tensorflow, Pytorch, etc.)
            version (str): Framework version
            
        Returns:
            tuple: (success, message)
        """
        command = f"/opt/aime-ml-containers/mlc-create {container_name} {framework} {version}"
        return self.execute_command(command)
    
    def open_container(self, container_name):
        """
        Open an existing container.
        
        Args:
            container_name (str): Name of the container to open
            
        Returns:
            tuple: (success, message)
        """
        command = f"/opt/aime-ml-containers/mlc-open {container_name}"
        return self.execute_command(command)
    
    def get_gpu_usage(self):
        """
        Get GPU usage information.
        
        Returns:
            tuple: (success, output)
        """
        return self.execute_command("nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits")
    
    def find_least_loaded_gpu(self):
        """
        Find the GPU with the lowest utilization.
        
        Returns:
            int: GPU ID with lowest utilization
        """
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

    def start_jupyter(self, container_name, _ignored_port):
        """
        Start JupyterLab in container using tmux; auth disabled, robust.
        
        Args:
            container_name (str): Name of the container
            _ignored_port: Ignored parameter for compatibility
            
        Returns:
            tuple: (success, message, token, metadata)
        """
        try:
            # ensure container
            self.execute_command(f"/opt/aime-ml-containers/mlc-start {container_name}")
            time.sleep(1)

            ok, container_id = self.execute_command(
                f"docker ps --filter 'name={container_name}' --format '{{{{.ID}}}}'"
            )
            if not ok or not container_id.strip():
                return False, "Container not found", None, None
            cid = container_id.strip()

            # Create script using base64 encoding to avoid quoting issues
            script_content = '''#!/usr/bin/env bash
set -euo pipefail
cd /workspace || { mkdir -p /workspace; cd /workspace; }
export HOME=/workspace
export JUPYTER_RUNTIME_DIR=/workspace/.jupyter/runtime
export JUPYTER_DATA_DIR=/workspace/.jupyter
export JUPYTER_CONFIG_DIR=/workspace/.jupyter
mkdir -p "$JUPYTER_RUNTIME_DIR" "$JUPYTER_CONFIG_DIR"
export JUPYTER_TOKEN=''
export JUPYTER_PASSWORD=''
echo 'c = get_config(); c.NotebookApp.token=""; c.NotebookApp.password=""' > /workspace/.jupyter/jupyter_notebook_config.py
exec jupyter notebook --no-browser --ip=0.0.0.0 --port=8888 --allow-root --NotebookApp.token='' --NotebookApp.password=''
'''
            
            # Encode script content to base64
            script_encoded = base64.b64encode(script_content.encode()).decode()
            
            # Write script using base64 decode
            ok, _ = self.execute_command(f"docker exec {cid} bash -c 'echo {script_encoded} | base64 -d > /workspace/start_jlab.sh'")
            if not ok: return False, "Failed to write script content", None, None
            
            # Make executable
            ok, _ = self.execute_command(f"docker exec {cid} bash -c 'chmod +x /workspace/start_jlab.sh'")
            if not ok: return False, "Failed to make script executable", None, None

            # run via tmux (robust) or background
            ok, out = self.execute_command(
                f"docker exec {cid} bash -lc "
                "\"if command -v tmux >/dev/null 2>&1; then "
                "S=jup-$(hostname)-$RANDOM; tmux new-session -d -s $S '/workspace/start_jlab.sh'; echo tmux_ok; "
                "else echo tmux_missing; fi\""
            )
            if not ok: return False, out, None, None
            if "tmux_missing" in out:
                ok, out = self.execute_command(f"docker exec -d {cid} bash -lc \"/workspace/start_jlab.sh > /workspace/jupyter.log 2>&1\"")
                if not ok: return False, out, None, None

            # Wait longer for Jupyter to start
            time.sleep(5)

            # find actual port and url (no token)
            ok, info = self.execute_command(
                f"docker exec {cid} bash -c 'cd /workspace && . nimaenv/bin/activate && "
                "jupyter server list --json 2>/dev/null || jupyter lab list --json 2>/dev/null'"
            )
            if not ok or not info.strip():
                # Try alternative approach - check if jupyter is running
                ok, ps_output = self.execute_command(f"docker exec {cid} bash -c 'ps aux | grep jupyter'")
                if ok and 'jupyter' in ps_output:
                    # Jupyter is running but we can't get the list, try to find port manually
                    ok, netstat = self.execute_command(f"docker exec {cid} bash -c 'netstat -tlnp 2>/dev/null | grep jupyter || ss -tlnp 2>/dev/null | grep jupyter'")
                    if ok and netstat.strip():
                        # Extract port from netstat output
                        port_match = re.search(r':(\d+)', netstat)
                        if port_match:
                            actual_port = int(port_match.group(1))
                            # Get container IP
                            ok, ip_out = self.execute_command(
                                f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {cid}"
                            )
                            if ok and ip_out.strip():
                                return True, f"JupyterLab up (no token)", None, {"port": actual_port, "ip": ip_out.strip()}
                    
                    # If netstat didn't work, try parsing the log file
                    ok, log_output = self.execute_command(f"docker exec {cid} bash -c 'tail -20 /workspace/jupyter.log'")
                    if ok and log_output.strip():
                        # Look for port in the log
                        # First try to find a specific port
                        port_match = re.search(r'http://[^:]+:(\d+)/', log_output)
                        if port_match and port_match.group(1) != '0':
                            actual_port = int(port_match.group(1))
                            # Get container IP - try multiple approaches
                            ok, ip_out = self.execute_command(
                                f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {cid}"
                            )
                            if not ok or not ip_out.strip():
                                # Try alternative approach
                                ok, ip_out = self.execute_command(
                                    f"docker inspect {cid} | grep -A 10 'NetworkSettings' | grep 'IPAddress' | head -1 | cut -d'\"' -f4"
                                )
                            
                            if ok and ip_out.strip():
                                return True, f"JupyterLab up (no token)", None, {"port": actual_port, "ip": ip_out.strip()}
                            else:
                                # Use localhost as fallback
                                return True, f"JupyterLab up (no token)", None, {"port": actual_port, "ip": "localhost"}
                        else:
                            # If port is 0, try to find the actual port from ss
                            ok, ss_output = self.execute_command(f"docker exec {cid} bash -c 'ss -tlnp 2>/dev/null | grep python3'")
                            if ok and ss_output.strip():
                                port_match = re.search(r':(\d+)\s', ss_output)
                                if port_match:
                                    actual_port = int(port_match.group(1))
                                else:
                                    return False, "Could not determine actual port", None, None
                            else:
                                # Try lsof as last resort
                                ok, lsof_output = self.execute_command(f"docker exec {cid} bash -c 'lsof -i -P -n 2>/dev/null | grep python3'")
                                if ok and lsof_output.strip():
                                    port_match = re.search(r':(\d+)', lsof_output)
                                    if port_match:
                                        actual_port = int(port_match.group(1))
                                    else:
                                        return False, "Could not determine actual port", None, None
                                else:
                                    return False, "Could not find Jupyter port", None, None
                            # Get container IP
                            ok, ip_out = self.execute_command(
                                f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {cid}"
                            )
                            if ok and ip_out.strip():
                                return True, f"JupyterLab up (no token)", None, {"port": actual_port, "ip": ip_out.strip()}
                
                return False, "Could not read jupyter server list", None, None

            # parse port from JSON lines (avoid jq)
            actual_port = None
            for line in info.splitlines():
                try:
                    obj = json.loads(line)
                    actual_port = int(obj.get('port')) if obj.get('port') else None
                    if actual_port: break
                except:  # not json
                    m = re.search(r':(\d+)', line)
                    if m: actual_port = int(m.group(1)); break
            if not actual_port:
                return False, f"Could not parse port from: {info}", None, None

            # container IP
            ok, ip_out = self.execute_command(
                f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {cid}"
            )
            if not ok or not ip_out.strip():
                return False, "Could not determine container IP", None, None

            return True, f"JupyterLab up (no token)", None, {"port": actual_port, "ip": ip_out.strip()}
        except Exception as e:
            return False, f"Error starting Jupyter: {e}", None, None

    def setup_port_forwarding(self, remote_host, remote_port, local_port):
        """
        Set up SSH tunnel for port forwarding.
        
        Args:
            remote_host (str): Remote host IP
            remote_port (int): Remote port number
            local_port (int): Local port number
            
        Returns:
            tuple: (success, message)
        """
        subprocess.run(f"lsof -ti:{local_port} | xargs kill -9", shell=True, capture_output=True)
        cmd = (
            f"sshpass -p '{self.password}' ssh -f -N "
            f"-o ExitOnForwardFailure=yes -o ServerAliveInterval=30 "
            f"-L {local_port}:{remote_host}:{remote_port} "
            f"{self.email}@{self.server_host}"
        )
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return False, res.stderr
        return True, f"localhost:{local_port} → {remote_host}:{remote_port}"
    
    def cleanup(self):
        """Clean up SSH connection and tunnel."""
        print(f"🧹 Cleaning up SSH tunnel and connection...")
        
        # Clean up SSH tunnel process with reduced timeout
        if self.ssh_tunnel_process:
            try:
                print(f"🛑 Terminating SSH tunnel process...")
                self.ssh_tunnel_process.terminate()
                self.ssh_tunnel_process.wait(timeout=2)  # Reduced from 5 to 2 seconds
                print(f"✅ SSH tunnel process terminated")
            except:
                print(f"⚠️ Force killing SSH tunnel process...")
                self.ssh_tunnel_process.kill()
        
        # Clean up SSH client with timeout
        if self.ssh_client:
            try:
                print(f"🔌 Closing SSH connection...")
                # Set a shorter timeout for SSH operations
                transport = self.ssh_client.get_transport()
                if transport:
                    transport.set_keepalive(5)  # Reduce keepalive
                self.ssh_client.close()
                print(f"✅ SSH connection closed")
            except Exception as e:
                print(f"⚠️ Error closing SSH connection: {e}")
        
        # Clean up any remaining SSH processes on local ports (non-blocking)
        if self.local_port:
            try:
                print(f"🧹 Cleaning up local port {self.local_port}...")
                # Use non-blocking cleanup with shorter timeout
                cleanup_cmd = f"timeout 3 lsof -ti:{self.local_port} | xargs kill -9 2>/dev/null || true"
                subprocess.run(cleanup_cmd, shell=True, capture_output=True, timeout=3)
                print(f"✅ Local port {self.local_port} cleaned up")
            except subprocess.TimeoutExpired:
                print(f"⚠️ Port cleanup timeout for {self.local_port}")
            except Exception as e:
                print(f"⚠️ Error cleaning up local port {self.local_port}: {e}")
    
    def stop_jupyter(self, container_name, _ignored_port=None):
        """
        Stop JupyterLab session using tmux.
        
        Args:
            container_name (str): Name of the container
            _ignored_port: Ignored parameter for compatibility
            
        Returns:
            tuple: (success, message)
        """
        try:
            print(f"🛑 Stopping JupyterLab in container: {container_name}")
            
            # Get container ID
            container_id_cmd = f"docker ps --filter 'name={container_name}' --format '{{{{.ID}}}}'"
            success, container_id = self.execute_command(container_id_cmd)
            if not success or not container_id.strip():
                return False, f"Could not find container ID for {container_name}"
            
            container_id = container_id.strip()
            
            # Kill all tmux sessions for this container
            stop_cmd = f"docker exec {container_id} bash -c 'tmux list-sessions 2>/dev/null | grep jup-{container_name} | cut -d: -f1 | xargs -I {{}} tmux kill-session -t {{}} && echo \"Sessions killed\" || echo \"No sessions found\"'"
            success, output = self.execute_command(stop_cmd)
            
            if success and "Sessions killed" in output:
                print(f"✅ JupyterLab sessions stopped for container: {container_name}")
                return True, f"JupyterLab sessions stopped for container: {container_name}"
            else:
                print(f"⚠️ No sessions found or already stopped for container: {container_name}")
                return True, f"JupyterLab sessions already stopped for container: {container_name}"
                
        except Exception as e:
            print(f"❌ Error stopping Jupyter: {str(e)}")
            return False, f"Error stopping Jupyter: {str(e)}"

    def create_interactive_shell(self, container_name=None):
        """
        Create an interactive shell session.
        
        Args:
            container_name (str): Optional container name to execute shell inside
            
        Returns:
            paramiko.Channel: SSH channel for interactive shell
        """
        if not self.ssh_client:
            raise Exception("No SSH connection established")
        
        # Create interactive shell channel
        channel = self.ssh_client.invoke_shell()
        channel.settimeout(0.1)  # Non-blocking
        
        # If container is specified, execute shell inside it
        if container_name:
            # First, ensure container is running
            self.execute_command(f"/opt/aime-ml-containers/mlc-start {container_name}")
            time.sleep(1)
            
            # Get container ID
            success, container_id = self.execute_command(
                f"docker ps --filter 'name={container_name}' --format '{{{{.ID}}}}'"
            )
            if not success or not container_id.strip():
                raise Exception(f"Container {container_name} not found")
            
            container_id = container_id.strip()
            
            # Send command to enter container
            channel.send(f"docker exec -it {container_id} bash\n")
            time.sleep(1)
        
        return channel
    
    def get_jupyter_token(self, container_name):
        """
        Get JupyterLab status (authentication disabled - no token needed).
        
        Args:
            container_name (str): Name of the container
            
        Returns:
            tuple: (success, message, token)
        """
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
