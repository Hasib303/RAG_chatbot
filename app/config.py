from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(slots=True)
class Settings:
    app_name: str = "Document Grounded Chatbot"
    root_dir: Path = ROOT_DIR
    data_dir: Path = root_dir / "data"
    uploads_dir: Path = data_dir / "uploads"
    indexes_dir: Path = data_dir / "indexes"
    frontend_dir: Path = root_dir / "app" / "frontend"
    static_dir: Path = frontend_dir / "static"
    index_file: Path = frontend_dir / "templates" / "index.html"

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
    ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

    chunk_size_chars: int = int(os.getenv("CHUNK_SIZE_CHARS", "900"))
    chunk_overlap_chars: int = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "4"))
    retrieval_score_threshold: float = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.35"))
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "8"))

    firebase_credentials_path: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    firebase_api_key: str = os.getenv("FIREBASE_API_KEY", "")
    firebase_auth_domain: str = os.getenv("FIREBASE_AUTH_DOMAIN", "")
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    firebase_storage_bucket: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")
    firebase_app_id: str = os.getenv("FIREBASE_APP_ID", "")
    firebase_messaging_sender_id: str = os.getenv("FIREBASE_MESSAGING_SENDER_ID", "")

    def ensure_directories(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

    @property
    def firebase_is_configured(self) -> bool:
        required = [
            self.firebase_credentials_path,
            self.firebase_api_key,
            self.firebase_auth_domain,
            self.firebase_project_id,
            self.firebase_app_id,
            self.firebase_messaging_sender_id,
        ]
        return all(required)

    @property
    def firebase_frontend_config(self) -> dict[str, str]:
        return {
            "apiKey": self.firebase_api_key,
            "authDomain": self.firebase_auth_domain,
            "projectId": self.firebase_project_id,
            "storageBucket": self.firebase_storage_bucket,
            "appId": self.firebase_app_id,
            "messagingSenderId": self.firebase_messaging_sender_id,
        }


settings = Settings()
settings.ensure_directories()
