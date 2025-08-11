#!/usr/bin/env python3
"""
Test script for container removal with interactive input handling
"""

import paramiko
import time
import json

# SSH Configuration
SERVER_HOST = "10.1.23.20"
EMAIL = "N.Thing@students.hertie-school.org"
PASSWORD = "Nimolearns@1121"

def test_container_removal():
    print("🔧 Testing Container Removal with Interactive Input")
    print("=" * 50)
    
    # Create SSH client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("🔗 Connecting to SSH...")
        ssh.connect(SERVER_HOST, username=EMAIL, password=PASSWORD, timeout=30)
        print("✅ SSH connection successful")
        
        # First, let's see what containers exist
        print("\n📋 Checking container list...")
        stdin, stdout, stderr = ssh.exec_command("/opt/aime-ml-containers/mlc-list", timeout=30)
        container_list = stdout.read().decode("utf-8", errors="ignore")
        print(f"Container list:\n{container_list}")
        
        # Find a test container to remove (preferably one that's already stopped)
        lines = container_list.strip().split('\n')
        test_container = None
        for line in lines:
            if 'test-fresh' in line and 'Exited' in line:
                parts = line.split()
                if len(parts) >= 1:
                    test_container = parts[0].strip('[]')
                    break
        
        if not test_container:
            print("❌ No suitable test container found (looking for exited containers)")
            # Try to find any test container and stop it first
            for line in lines:
                if 'test-fresh' in line and 'Up' in line:
                    parts = line.split()
                    if len(parts) >= 1:
                        test_container = parts[0].strip('[]')
                        print(f"🎯 Found running test container: {test_container}")
                        print("🛑 Stopping it first...")
                        
                        # Stop the container
                        stdin, stdout, stderr = ssh.exec_command(f"/opt/aime-ml-containers/mlc-stop {test_container} -Y", timeout=30)
                        exit_status = stdout.channel.recv_exit_status()
                        output = stdout.read().decode("utf-8", errors="ignore")
                        print(f"Stop result: {output}")
                        
                        if exit_status == 0:
                            print("✅ Container stopped successfully")
                            time.sleep(3)  # Wait for stop to take effect
                            break
                        else:
                            test_container = None
                            continue
        
        if not test_container:
            print("❌ No suitable test container found")
            return False
            
        print(f"\n🎯 Found test container: {test_container}")
        
        # Test the mlc-remove command with interactive input
        print(f"\n🗑️ Testing mlc-remove for {test_container} with interactive input...")
        print("Command: /opt/aime-ml-containers/mlc-remove " + test_container)
        
        # Use pseudo-terminal for interactive input
        stdin, stdout, stderr = ssh.exec_command(f"/opt/aime-ml-containers/mlc-remove {test_container}", get_pty=True, timeout=60)
        
        # Wait a moment for the prompt to appear
        time.sleep(2)
        
        # Send 'Y' to confirm deletion
        if stdin:
            stdin.write('Y\n')
            stdin.flush()
            print("✅ Sent 'Y' confirmation")
        
        # Wait for completion
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore")
        error = stderr.read().decode("utf-8", errors="ignore")
        
        print(f"Exit status: {exit_status}")
        print(f"Output: {output}")
        print(f"Error: {error}")
        
        if exit_status == 0:
            print("✅ Container removal successful!")
            
            # Verify removal
            print("\n🔍 Verifying removal...")
            stdin, stdout, stderr = ssh.exec_command("/opt/aime-ml-containers/mlc-list", timeout=30)
            updated_list = stdout.read().decode("utf-8", errors="ignore")
            print(f"Updated container list:\n{updated_list}")
            
            if test_container not in updated_list:
                print("✅ Container successfully removed from list!")
                return True
            else:
                print("❌ Container still appears in list")
                return False
        else:
            print("❌ Container removal failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ssh.close()

if __name__ == "__main__":
    success = test_container_removal()
    exit(0 if success else 1)
