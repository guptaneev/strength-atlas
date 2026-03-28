from __future__ import annotations

import json
from typing import Any

import httpx

from atlas.config.settings import get_settings


class SupabaseStorageClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.supabase_url:
            raise RuntimeError("ATLAS_SUPABASE_URL is required")
        if not settings.supabase_service_key:
            raise RuntimeError("ATLAS_SUPABASE_SERVICE_KEY is required")
        if not settings.supabase_storage_bucket:
            raise RuntimeError("ATLAS_SUPABASE_STORAGE_BUCKET is required")
        self._base_url = settings.supabase_url.rstrip("/")
        self._service_key = settings.supabase_service_key
        self._bucket = settings.supabase_storage_bucket

    def upload_bytes(self, object_path: str, payload: bytes, content_type: str) -> None:
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{object_path}"
        headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, content=payload, headers=headers)
            response.raise_for_status()

    def upload_text(self, object_path: str, text: str, content_type: str) -> None:
        self.upload_bytes(object_path, text.encode("utf-8"), content_type)

    def upload_json(self, object_path: str, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str)
        self.upload_text(object_path, body, "application/json")
