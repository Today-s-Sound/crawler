import os
from typing import List, Dict, Optional
from sites.dongguk_sw_board import DonggukSwBoardCrawler
from services.subscription_client import fetch_subscriptions
from services.notification_client import create_alert, update_subscription_last_seen
from services.summarizer import summarize


def filter_new_posts(posts: List[Dict], last_seen_post_id: Optional[str]) -> List[Dict]:
    """
    posts: 최신→오래된 순
    last_seen_post_id: None이면 '새로 본 게 없다'고 가정하고, 이번에는 새 알림 안 만듦.
    return: 지난번 이후 새로 올라온 게시물들 (오래된→최신 순)
    """
    if last_seen_post_id is None:
        return []

    new_posts = []
    for post in posts:
        if post["id"] == last_seen_post_id:
            break
        new_posts.append(post)

    new_posts.reverse()
    return new_posts

def keyword_match(keyword: Optional[str], text: str) -> bool:
    if not keyword:
        return True  # 키워드 없으면 전부 매칭
    return keyword in text  # 간단한 포함 여부 (나중에 개선 가능)

# “구독 하나에 대해 ‘이번 턴에 새로 생긴 알림’을 DB에 쌓는 단위 작업”
def process_subscription(sub: Dict):
    # 사이트 타입 식별 로직 (지금은 동국대 SW게시판 하나만)
    # 지금은 “모든 구독이 다 동국대 SW게시판이다”라고 가정하는 상태.
    # 나중에는 sub["site_type"] 같은 필드로 사이트 종류를 보고,
    # if site_type == "DONGGUK_SW": DonggukSwBoardCrawler() 이런 식으로 분기할 예정
    # 이런 식으로 분기할 예정이라 TODO로 남겨둔 것.
    
    crawler = DonggukSwBoardCrawler()

    posts = crawler.fetch_post_list(sub["site_url"])
    if not posts:
        return

    last_seen_id = sub.get("last_seen_post_id")
    latest_id = posts[0]["id"]

    # 첫 실행: 기준점만 설정 (알림 생성 X) -> 이미 올라와 있던 글들은 과거 글이라고 생각하고 무시.
    if last_seen_id is None:
        print(f"[Sub {sub['id']}] 첫 실행 - 기준점만 설정 (last_seen_post_id={latest_id})")
        update_subscription_last_seen(sub["id"], latest_id)
        return

    new_posts = filter_new_posts(posts, last_seen_id)

    if not new_posts: 
        print(f"[Sub {sub['id']}] 새 게시물 없음")
        return

    print(f"[Sub {sub['id']}] 새 게시물 {len(new_posts)}개")

    for post in new_posts: # 새로 올라온 게시물들(여러 개일 수도 있음)을 하나씩 순회.
        content_raw = crawler.fetch_post_content(post["url"])

        # 키워드 필터
        if not keyword_match(sub.get("keyword"), post["title"] + " " + content_raw):
            print(f"  - 키워드 불일치로 스킵: {post['title']}")
            continue

        summary = summarize(content_raw)

        # 알림 생성 요청 데이터 생성
        alert_payload = {
            "user_id": sub["user_id"],
            "subscription_id": sub["id"],
            "site_post_id": post["id"],
            "title": post["title"],
            "url": post["url"],
            "content_raw": content_raw, # 원문 전체 텍스트 
            "content_summary": summary, # 요약 텍스트
            "is_urgent": sub["urgent"],
        }

        create_alert(alert_payload)

    # 마지막으로 last_seen_post_id 갱신
    update_subscription_last_seen(sub["id"], latest_id)


def main():
    subs = fetch_subscriptions()
    print(f"총 구독 수: {len(subs)}")

    for sub in subs:
        try:
            process_subscription(sub)
        except Exception as e:
            print(f"[Sub {sub['id']}] 처리 중 오류: {e}")

if __name__ == "__main__":
    main()


# def debug_fetch_first_post():
#     """
#     첫 번째 구독의 첫 번째 게시물 목록/본문이 정상적으로 크롤링되는지 확인용 디버그 함수.
#     크롤링/요약/알림과는 무관하게, 크롤링 자체가 잘 되는지만 확인할 때 사용.
#     """
#     subs = fetch_subscriptions()
#     print(f"[DEBUG] 구독 개수: {len(subs)}")
#     if not subs:
#         print("[DEBUG] 구독이 없습니다.")
#         return

#     sub = subs[0]
#     print(f"[DEBUG] 첫 구독 ID={sub.get('id')}, site_url={sub.get('site_url')}")

#     crawler = DonggukSwBoardCrawler()
#     posts = crawler.fetch_post_list(sub["site_url"])
#     print(f"[DEBUG] 게시물 개수: {len(posts)}")
#     if not posts:
#         print("[DEBUG] 게시물이 없습니다.")
#         return

#     first_post = posts[0]
#     print(f"[DEBUG] 첫 게시물 메타데이터: {first_post}")

#     content_raw = crawler.fetch_post_content(first_post["url"])
#     print("[DEBUG] 첫 게시물 본문 (앞 500자):")
#     print(content_raw[:2000])

#     # 요약기(summarizer)를 통한 요약 결과 확인
#     # summary = summarize(content_raw)
#     # print("\n[DEBUG] 요약 결과:")
#     # print(summary)


# if __name__ == "__main__":
#     if True:
#         debug_fetch_first_post()
#     else:
#         main()