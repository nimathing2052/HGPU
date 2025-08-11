#!/usr/bin/env python3
"""
Port Management Utilities
Handles port discovery, cleanup, and management for the GPU server application.
"""

import subprocess
import sys

def find_available_local_port(port_range):
    """
    Find an available local port for forwarding.
    
    Args:
        port_range: Range of ports to check (can be range object or tuple)
        
    Returns:
        int or None: Available port number or None if none found
    """
    # Convert tuple to range if needed
    if isinstance(port_range, tuple):
        port_range = range(port_range[0], port_range[1] + 1)
    
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
    """
    Find an available port for Flask app.
    
    Returns:
        int or None: Available port number or None if none found
    """
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

def cleanup_all_ports(port_range):
    """
    Clean up all SSH tunnels and processes on local ports.
    
    Args:
        port_range: Range of ports to clean up
    """
    print(f"🧹 Global port cleanup initiated...")
    
    try:
        # More efficient bulk cleanup approach
        port_list = list(port_range)
        if not port_list:
            return
        
        # Create a single command to check all ports at once
        ports_str = ','.join(map(str, port_list))
        bulk_cleanup_cmd = f"lsof -ti:{ports_str} | xargs kill -9 2>/dev/null || true"
        
        # Run bulk cleanup with timeout
        result = subprocess.run(bulk_cleanup_cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            print(f"✅ Bulk cleaned up ports in range")
        
        # Also kill any ssh processes that might be hanging (with timeout)
        ssh_cleanup = "timeout 3 pkill -f 'ssh.*-L.*localhost' 2>/dev/null || true"
        subprocess.run(ssh_cleanup, shell=True, capture_output=True, timeout=3)
        print(f"✅ Cleaned up SSH tunnel processes")
        
    except subprocess.TimeoutExpired:
        print(f"⚠️ Port cleanup timeout - continuing...")
    except Exception as e:
        print(f"⚠️ Error during global port cleanup: {e}")

def cleanup_specific_port(port):
    """
    Clean up a specific port.
    
    Args:
        port (int): Port number to clean up
    """
    try:
        cleanup_cmd = f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
        subprocess.run(cleanup_cmd, shell=True, capture_output=True)
        print(f"✅ Cleaned up port {port}")
    except Exception as e:
        print(f"⚠️ Error cleaning up port {port}: {e}")

def check_port_usage(port):
    """
    Check if a specific port is in use.
    
    Args:
        port (int): Port number to check
        
    Returns:
        bool: True if port is in use, False otherwise
    """
    try:
        result = subprocess.run(f"lsof -i:{port}", shell=True, capture_output=True)
        return result.returncode == 0
    except Exception:
        return False
