import requests
import os
from typing import Dict

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8080")

def create_alert(alert: Dict) -> None:
    """
    alert 예시:
    {
      "user_id": 10,
      "subscription_id": 1,
      "site_alias": "동국대 SW공지",
      "site_post_id": "12345",
      "title": "...",
      "url": "https://...",
      "published_at": "2025-11-14",
      "content_raw": "...",
      "content_summary": "...",
      "keyword_matched": true
    }
    """
    res = requests.post(f"{BACKEND_BASE_URL}/internal/alerts", json=alert)
    res.raise_for_status()

def update_subscription_last_seen(subscription_id: int, last_seen_post_id: str) -> None:
    """
    백엔드(https://www.todaysound.com/internal/subscriptions/{subscription_id}/last_seen)에
    PATCH 요청을 보내서 last_seen_post_id를 업데이트한다.
    요청이 실패하면 예외를 던지고, 성공하면 무시.
    """
    res = requests.patch(
        f"{BACKEND_BASE_URL}/internal/subscriptions/{subscription_id}/last_seen",
        json={"last_seen_post_id": last_seen_post_id},
    )
    res.raise_for_status()