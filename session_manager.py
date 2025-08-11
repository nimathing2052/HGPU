#!/usr/bin/env python3
"""
Session Management Module
Handles user sessions, authentication, and session cleanup for the GPU server application.
"""

import time
import threading
from typing import Dict, Any, Optional
import concurrent.futures

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
                
                # Cleanup manager resources with timeout
                if hasattr(manager, 'cleanup'):
                    try:
                        # Use threading to avoid blocking
                        cleanup_thread = threading.Thread(
                            target=self._cleanup_manager_with_timeout,
                            args=(manager, session_id),
                            daemon=True
                        )
                        cleanup_thread.start()
                        cleanup_thread.join(timeout=10)  # 10 second timeout
                        
                        if cleanup_thread.is_alive():
                            print(f"⚠️ Cleanup timeout for session: {session_id}")
                    except Exception as e:
                        print(f"⚠️ Error cleaning up manager for session {session_id}: {e}")
                
                # Remove session
                del self.sessions[session_id]
                print(f"🗑️ Session removed: {session_id}")
                return True
            return False
    
    def _cleanup_manager_with_timeout(self, manager, session_id: str) -> None:
        """Cleanup manager with timeout handling."""
        try:
            manager.cleanup()
            print(f"🧹 Cleaned up manager for session: {session_id}")
        except Exception as e:
            print(f"⚠️ Error in cleanup thread for session {session_id}: {e}")
    
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
        
        if not session_ids:
            print(f"✅ No active sessions to cleanup")
            return
        
        print(f"🔄 Cleaning up {len(session_ids)} active sessions...")
        
        # Use ThreadPoolExecutor for parallel cleanup with timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(session_ids), 5)) as executor:
            # Submit cleanup tasks
            future_to_session = {}
            for session_id in session_ids:
                future = executor.submit(self._cleanup_session_async, session_id)
                future_to_session[future] = session_id
            
            # Wait for completion with timeout
            try:
                for future in concurrent.futures.as_completed(future_to_session, timeout=30):
                    session_id = future_to_session[future]
                    try:
                        future.result(timeout=5)  # Individual task timeout
                    except concurrent.futures.TimeoutError:
                        print(f"⚠️ Cleanup timeout for session: {session_id}")
                    except Exception as e:
                        print(f"⚠️ Error cleaning up session {session_id}: {e}")
            except concurrent.futures.TimeoutError:
                print(f"⚠️ Overall cleanup timeout after 30 seconds")
        
        print(f"✅ Session manager shutdown complete")
    
    def _cleanup_session_async(self, session_id: str) -> None:
        """Asynchronous session cleanup for parallel execution."""
        with self._lock:
            if session_id not in self.sessions:
                return
            
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

# Global session manager instance
session_manager = SessionManager()
