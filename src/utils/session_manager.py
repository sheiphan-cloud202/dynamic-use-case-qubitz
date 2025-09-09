"""
Session management for the Business Transformation Agent.
"""
import json
import hashlib
import threading
from datetime import datetime
from typing import Dict

class SessionManager:
    """Manages active sessions to prevent duplicate processing."""
    
    def __init__(self):
        self._active_sessions: Dict[str, Dict] = {}
        self._session_lock = threading.Lock()

    def generate_session_key(self, payload: Dict) -> str:
        """Generate a unique session key based on payload."""
        # Create a normalized payload for consistent hashing
        normalized_payload = {
            'company_name': payload.get('company_name', '').strip().lower(),
            'company_url': payload.get('company_url', '').strip().lower(),
            'action': payload.get('action', 'start')
        }
        
        # Include custom prompt in session key
        if 'prompt' in payload and payload['prompt']:
            normalized_payload['prompt_hash'] = hashlib.md5(payload['prompt'].encode()).hexdigest()[:16]
        
        # Include files in session key
        if 'files' in payload and payload['files']:
            file_hashes = []
            for file_url in payload['files']:
                file_hashes.append(hashlib.md5(file_url.encode()).hexdigest()[:8])
            normalized_payload['file_hashes'] = sorted(file_hashes)
        
        # For select_use_cases action, include selected use case IDs
        if normalized_payload['action'] == 'select_use_cases':
            normalized_payload['selected_use_case_ids'] = sorted(payload.get('selected_use_case_ids', []))
        
        # Generate hash
        payload_str = json.dumps(normalized_payload, sort_keys=True)
        return hashlib.md5(payload_str.encode()).hexdigest()

    def is_session_active(self, session_key: str) -> bool:
        """Check if a session is currently active."""
        with self._session_lock:
            return session_key in self._active_sessions

    def start_session(self, session_key: str, payload: Dict) -> bool:
        """Start a new session. Returns True if started, False if already active."""
        with self._session_lock:
            if session_key in self._active_sessions:
                return False
            
            self._active_sessions[session_key] = {
                'started_at': datetime.now().isoformat(),
                'payload': payload,
                'status': 'in_progress'
            }
            return True

    def complete_session(self, session_key: str, result: Dict = None):
        """Mark session as complete and remove from active sessions."""
        with self._session_lock:
            if session_key in self._active_sessions:
                self._active_sessions[session_key]['status'] = 'completed'
                self._active_sessions[session_key]['completed_at'] = datetime.now().isoformat()
                if result:
                    self._active_sessions[session_key]['result'] = result
                # Remove from active sessions after a short delay to allow status checks
                del self._active_sessions[session_key]

    def get_session_info(self, session_key: str) -> Dict:
        """Get session information."""
        with self._session_lock:
            return self._active_sessions.get(session_key, {})
