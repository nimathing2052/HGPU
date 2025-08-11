#!/usr/bin/env python3
"""
Session Management Module
Handles user sessions, authentication, and session cleanup for the GPU server application.
"""

import time
import threading
from typing import Dict, Any, Optional

class SessionManager:
    """Manages user sessions and authentication state."""
    
    def __init__(self, session_timeout: int = 3600):
        """
        Initialize the session manager.
        
        Args:
            session_timeout (int): Session timeout in seconds (default: 1 hour)
        """
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = session_timeout
        self._lock = threading.Lock()
        
        # Start cleanup thread (disabled for now to avoid threading issues)
        # self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        # self._cleanup_thread.start()
    
    def create_session(self, session_id: str, manager: Any, email: str) -> None:
        """
        Create a new user session.
        
        Args:
            session_id (str): Unique session identifier
            manager: GPU server manager instance
            email (str): User email
        """
        with self._lock:
            self.sessions[session_id] = {
                'manager': manager,
                'email': email,
                'created_at': time.time(),
                'last_activity': time.time()
            }
            print(f"✅ Session created: {session_id} for {email}")
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID.
        
        Args:
            session_id (str): Session identifier
            
        Returns:
            Dict or None: Session data if found and valid, None otherwise
        """
        with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                # Update last activity
                session['last_activity'] = time.time()
                return session
            return None
    
    def remove_session(self, session_id: str) -> bool:
        """
        Remove a session and cleanup resources.
        
        Args:
            session_id (str): Session identifier
            
        Returns:
            bool: True if session was removed, False if not found
        """
        with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                manager = session['manager']
                
                # Cleanup manager resources
                if hasattr(manager, 'cleanup'):
                    try:
                        manager.cleanup()
                        print(f"🧹 Cleaned up manager for session: {session_id}")
                    except Exception as e:
                        print(f"⚠️ Error cleaning up manager for session {session_id}: {e}")
                
                # Remove session
                del self.sessions[session_id]
                print(f"🗑️ Session removed: {session_id}")
                return True
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.
        
        Returns:
            int: Number of sessions removed
        """
        current_time = time.time()
        expired_sessions = []
        
        with self._lock:
            for session_id, session in self.sessions.items():
                if current_time - session['last_activity'] > self.session_timeout:
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                self.remove_session(session_id)
        
        if expired_sessions:
            print(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active sessions.
        
        Returns:
            Dict: Copy of active sessions
        """
        with self._lock:
            return self.sessions.copy()
    
    def get_session_count(self) -> int:
        """
        Get the number of active sessions.
        
        Returns:
            int: Number of active sessions
        """
        with self._lock:
            return len(self.sessions)
    
    def _cleanup_loop(self) -> None:
        """Background thread for periodic session cleanup."""
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes
                self.cleanup_expired_sessions()
            except Exception as e:
                print(f"⚠️ Error in cleanup loop: {e}")
    
    def shutdown(self) -> None:
        """Shutdown the session manager and cleanup all sessions."""
        print(f"🛑 Shutting down session manager...")
        with self._lock:
            session_ids = list(self.sessions.keys())
            for session_id in session_ids:
                self.remove_session(session_id)
        print(f"✅ Session manager shutdown complete")

# Global session manager instance
session_manager = SessionManager()
