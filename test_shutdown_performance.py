#!/usr/bin/env python3
"""
Test script to measure session manager shutdown performance improvements.
"""

import time
import threading
from session_manager import SessionManager
from gpu_manager import GPUServerManager

class MockGPUManger:
    """Mock GPU manager for testing cleanup performance."""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.cleanup_called = False
    
    def cleanup(self):
        """Simulate cleanup with variable delay."""
        print(f"🧹 Mock cleanup for session {self.session_id}")
        # Simulate cleanup time (0.5 to 2 seconds)
        time.sleep(0.5 + (hash(self.session_id) % 15) / 10)
        self.cleanup_called = True
        print(f"✅ Mock cleanup completed for session {self.session_id}")

def test_shutdown_performance():
    """Test shutdown performance with multiple sessions."""
    
    # Create session manager
    sm = SessionManager()
    
    # Create multiple mock sessions
    num_sessions = 10
    print(f"🔄 Creating {num_sessions} mock sessions...")
    
    for i in range(num_sessions):
        session_id = f"test_session_{i}"
        manager = MockGPUManger(session_id)
        sm.create_session(session_id, manager, f"user{i}@test.com")
    
    print(f"✅ Created {num_sessions} sessions")
    print(f"📊 Active sessions: {sm.get_session_count()}")
    
    # Test shutdown performance
    print(f"\n🛑 Testing shutdown performance...")
    start_time = time.time()
    
    sm.shutdown()
    
    end_time = time.time()
    shutdown_duration = end_time - start_time
    
    print(f"\n📈 Shutdown Performance Results:")
    print(f"   Sessions cleaned up: {num_sessions}")
    print(f"   Total shutdown time: {shutdown_duration:.2f} seconds")
    print(f"   Average per session: {shutdown_duration/num_sessions:.2f} seconds")
    print(f"   Remaining sessions: {sm.get_session_count()}")
    
    # Performance expectations
    if shutdown_duration < 15:  # Should be much faster with parallel processing
        print(f"✅ Performance: EXCELLENT (under 15 seconds)")
    elif shutdown_duration < 30:
        print(f"✅ Performance: GOOD (under 30 seconds)")
    else:
        print(f"⚠️ Performance: NEEDS IMPROVEMENT (over 30 seconds)")

if __name__ == "__main__":
    test_shutdown_performance()
