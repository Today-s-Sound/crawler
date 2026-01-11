import time
import requests
from typing import List, Dict
import os

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8080")

def fetch_subscriptions() -> List[Dict]:
    """
    백엔드(/internal/subscriptions)에 GET 요청을 보내서
    “활성화된 구독 목록”을 JSON으로 받는다.

    현재 백엔드 응답 형식(InternalSubscriptionResponseDto):
    {
      "errorCode": null,
      "message": "OK",
      "result": [
        {
          "id": 1,
          "user_id": 10,
          "site_url": "https://sw.dongguk.edu/board/list.do?id=S181",
          "site_alias": "동국대 SW공지",
          "keyword": "장학",
          "last_seen_post_id": "12345"  # 없으면 null 로 내려옴
        },
        ...
      ]
    }
    """
    try:
        res = requests.get(f"{BACKEND_BASE_URL}/internal/subscriptions", timeout=5)
        res.raise_for_status()  # 400 이상의 에러 발생 시 예외 발생
        data = res.json()
        # ApiResponse 래핑되어 있으므로 result 필드만 사용
        subs = data.get("result", [])
        if not isinstance(subs, list):
            # 혹시라도 단일 객체로 올 경우 리스트로 감싸기
            subs = [subs]
        return subs
    except requests.exceptions.RequestException as e:
        print("구독 목록 조회 실패:", e)
        raise

