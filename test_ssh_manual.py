#!/usr/bin/env python3
"""
Manual SSH test for mlc-remove command
"""

import paramiko
import time

# SSH Configuration
SERVER_HOST = "10.1.23.20"
EMAIL = "N.Thing@students.hertie-school.org"
PASSWORD = "Nimolearns@1121"

def test_manual_removal():
    print("🔧 Manual SSH Test for mlc-remove")
    print("=" * 40)
    
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
        
        # Find a test container to remove
        lines = container_list.strip().split('\n')
        test_container = None
        for line in lines:
            if 'test-fresh' in line and 'Exited' in line:
                parts = line.split()
                if len(parts) >= 1:
                    test_container = parts[0].strip('[]')
                    break
        
        if not test_container:
            print("❌ No suitable test container found")
            return False
            
        print(f"\n🎯 Found test container: {test_container}")
        
        # Test the mlc-remove command
        print(f"\n🗑️ Testing mlc-remove for {test_container}...")
        print("Command: /opt/aime-ml-containers/mlc-remove " + test_container)
        
        stdin, stdout, stderr = ssh.exec_command(f"/opt/aime-ml-containers/mlc-remove {test_container}", timeout=60)
        
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
        return False
    finally:
        ssh.close()

if __name__ == "__main__":
    success = test_manual_removal()
    exit(0 if success else 1)
