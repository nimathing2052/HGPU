#!/usr/bin/env python3
"""
Practical test script for token extraction with real session data
"""

import requests
import json
import sys

def get_user_input():
    """Get session ID and container name from user"""
    print("🔧 Token Extraction Test with Real Data")
    print("=" * 50)
    
    session_id = input("Enter your session ID: ").strip()
    if not session_id:
        print("❌ Session ID is required")
        return None, None
    
    container_name = input("Enter your container name: ").strip()
    if not container_name:
        print("❌ Container name is required")
        return None, None
    
    return session_id, container_name

def test_token_extraction(session_id, container_name):
    """Test token extraction with real data"""
    
    base_url = "http://localhost:2344"
    
    print(f"\n🧪 Testing with real data...")
    print(f"📤 Session ID: {session_id}")
    print(f"📤 Container: {container_name}")
    
    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Server is running (status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Server not running: {e}")
        return False
    
    # Test 2: Test get-jupyter-token endpoint
    print(f"\n🔧 Testing /get-jupyter-token endpoint...")
    test_data = {
        'session_id': session_id,
        'container_name': container_name
    }
    
    try:
        response = requests.post(
            f"{base_url}/get-jupyter-token",
            json=test_data,
            timeout=15
        )
        result = response.json()
        print(f"📥 Response: {result}")
        
        if result.get('success'):
            if result.get('token'):
                print(f"🎉 SUCCESS: Token extracted!")
                print(f"🔑 Token: {result['token']}")
                return True
            else:
                print(f"✅ SUCCESS: No token (authentication disabled)")
                return True
        else:
            print(f"❌ FAILED: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 3: Test launch-jupyter endpoint
    print(f"\n🔧 Testing /launch-jupyter endpoint...")
    try:
        response = requests.post(
            f"{base_url}/launch-jupyter",
            json=test_data,
            timeout=30
        )
        result = response.json()
        print(f"📥 Response: {result}")
        
        if result.get('success'):
            print(f"🎉 SUCCESS: Jupyter launched!")
            print(f"🌐 URL: {result.get('jupyter_url')}")
            if result.get('token'):
                print(f"🔑 Token: {result['token']}")
            else:
                print(f"✅ No token (authentication disabled)")
            return True
        else:
            print(f"❌ FAILED: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main test function"""
    
    # Get user input
    session_id, container_name = get_user_input()
    if not session_id or not container_name:
        print("❌ Invalid input. Exiting.")
        sys.exit(1)
    
    # Run tests
    success = test_token_extraction(session_id, container_name)
    
    if success:
        print(f"\n🎉 Token extraction test completed successfully!")
        print(f"✅ Your changes are working!")
    else:
        print(f"\n❌ Token extraction test failed.")
        print(f"💡 Check the Flask app logs for more details.")
    
    print(f"\n📝 Next steps:")
    print(f"1. Check the Flask app logs for detailed output")
    print(f"2. Try the 'Get Token' button in the web interface")
    print(f"3. Look for DEBUG output in the terminal")

if __name__ == "__main__":
    main()
