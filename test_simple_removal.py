#!/usr/bin/env python3
"""
Simple test to verify container removal functionality
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:2349"
EMAIL = "N.Thing@students.hertie-school.org"
PASSWORD = "Nimolearns@1121"

def test_removal():
    print("🧪 Simple Container Removal Test")
    print("=" * 40)
    
    # Step 1: Authenticate
    print("🔐 Step 1: Authenticating...")
    auth_data = {
        'email': EMAIL,
        'password': PASSWORD
    }
    
    try:
        response = requests.post(f"{BASE_URL}/authenticate", data=auth_data, timeout=30)
        result = response.json()
        
        if not result.get('success'):
            print(f"❌ Authentication failed: {result.get('message')}")
            return False
            
        session_id = result.get('session_id')
        print(f"✅ Authentication successful! Session ID: {session_id}")
        
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False
    
    # Step 2: Get container list
    print("\n📋 Step 2: Getting container list...")
    try:
        response = requests.get(f"{BASE_URL}/get-containers?session_id={session_id}", timeout=30)
        result = response.json()
        
        if not result.get('success'):
            print(f"❌ Failed to get containers: {result.get('message')}")
            return False
            
        containers = result.get('containers', [])
        print(f"✅ Found {len(containers)} containers")
        
        if not containers:
            print("❌ No containers found to test removal")
            return False
            
        # Find a container to remove (preferably one that's not running)
        test_container = None
        for container in containers:
            if 'test' in container['name'].lower():
                test_container = container
                break
        
        if not test_container:
            # Use the first container if no test container found
            test_container = containers[0]
            
        print(f"🎯 Selected container for removal: {test_container['name']} (Status: {test_container['status']})")
        
    except Exception as e:
        print(f"❌ Error getting containers: {e}")
        return False
    
    # Step 3: Remove container
    print(f"\n🗑️ Step 3: Removing container '{test_container['name']}'...")
    remove_data = {
        'session_id': session_id,
        'container_name': test_container['name']
    }
    
    try:
        response = requests.post(f"{BASE_URL}/remove-container", 
                               json=remove_data, 
                               timeout=60)
        result = response.json()
        
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response: {result}")
        
        if result.get('success'):
            print(f"✅ Container removal successful: {result.get('message')}")
        else:
            print(f"❌ Container removal failed: {result.get('message')}")
            return False
            
    except Exception as e:
        print(f"❌ Error during removal: {e}")
        return False
    
    # Step 4: Verify removal
    print("\n🔍 Step 4: Verifying container was removed...")
    time.sleep(3)  # Wait a bit for the removal to complete
    
    try:
        response = requests.get(f"{BASE_URL}/get-containers?session_id={session_id}", timeout=30)
        result = response.json()
        
        if not result.get('success'):
            print(f"❌ Failed to get updated container list: {result.get('message')}")
            return False
            
        updated_containers = result.get('containers', [])
        print(f"✅ Updated container list has {len(updated_containers)} containers")
        
        # Check if the removed container is still in the list
        removed_container_still_exists = any(
            container['name'] == test_container['name'] 
            for container in updated_containers
        )
        
        if removed_container_still_exists:
            print(f"❌ Container '{test_container['name']}' still exists in the list!")
            return False
        else:
            print(f"✅ Container '{test_container['name']}' successfully removed from the list!")
            
    except Exception as e:
        print(f"❌ Error verifying removal: {e}")
        return False
    
    print("\n🎉 Container removal test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_removal()
    exit(0 if success else 1)
