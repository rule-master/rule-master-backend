import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import uuid

class ChatSession:
    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.messages: List[Dict] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ChatSession':
        session = cls(session_id=data["session_id"])
        session.messages = data["messages"]
        session.created_at = data["created_at"]
        session.updated_at = data["updated_at"]
        return session

class ChatSessionManager:
    def __init__(self, storage_dir: str = "chat_sessions"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def save_session(self, session: ChatSession):
        file_path = os.path.join(self.storage_dir, f"{session.session_id}.json")
        with open(file_path, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)

    def load_session(self, session_id: str) -> Optional[ChatSession]:
        file_path = os.path.join(self.storage_dir, f"{session_id}.json")
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r') as f:
            data = json.load(f)
            return ChatSession.from_dict(data)

    def list_sessions(self) -> List[Dict]:
        sessions = []
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.storage_dir, filename)
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data["session_id"],
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "message_count": len(data["messages"])
                    })
        return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)

    def delete_session(self, session_id: str):
        file_path = os.path.join(self.storage_dir, f"{session_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path) 