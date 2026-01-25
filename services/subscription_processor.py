from typing import List, Dict

from sites.base import SiteCrawler
from services.alert_service import AlertService
from services.summarizer_service import SummarizerService
from services.cache_manager import CacheManager
from utils.post_filter import filter_new_posts, keyword_match


def process_subscription(
    sub: Dict,
    crawler: SiteCrawler,
    posts: List[Dict],
    alert_service: AlertService,
    summarizer_service: SummarizerService,
    cache_manager: CacheManager,
):
    """
    구독 하나에 대해 '이번 턴에 새로 생긴 알림'을 DB에 쌓는 단위 작업
    """
    # 이미 site_url 단위로 크롤링된 posts/ crawler 를 재사용
    print(f"[Sub {sub['id']}] site_url={sub['site_url']}")
    print(f"[Sub {sub['id']}] crawler={type(crawler).__name__}")

    if not posts:
        return

    last_seen_id = sub.get("last_seen_post_id")
    latest_id = posts[0]["id"]
    
    # 디버깅: last_seen_id 확인
    print(f"[Sub {sub['id']}] 🔍 last_seen_id={last_seen_id}, latest_id={latest_id}")

    # 첫 실행: 가장 최신 게시글 1개를 바로 요약·알림으로 보내고, 그 게시글을 기준점으로 설정.
    if last_seen_id is None:
        latest_post = posts[0]
        print(f"[Sub {sub['id']}] 첫 실행 - 최신 게시글 1개를 요약 및 알림 생성 (post_id={latest_id})")

        cache_key = latest_post.get("id") or latest_post["url"]
        if not cache_key:
            print(f"[Sub {sub['id']}] 캐시 키가 없어 스킵합니다")
            alert_service.update_subscription_last_seen(sub["id"], latest_id)
            return
        
        # 캐시에서 본문 가져오기
        content_raw = cache_manager.get_content(cache_key)
        if content_raw is None:
            content_raw = crawler.fetch_post_content(latest_post["url"])
            cache_manager.set_content(cache_key, content_raw)

        # 본문이 비어있으면 스킵 (크롤러가 본문 영역을 찾지 못한 경우)
        if not content_raw.strip():
            print(f"[Sub {sub['id']}] 본문이 비어있어 스킵합니다: {latest_post['url']}")
            alert_service.update_subscription_last_seen(sub["id"], latest_id)
            return

        # 키워드 매칭 여부 (있으면 포함 여부, 없으면 False)
        matched = keyword_match(sub.get("keyword"),
                                latest_post["title"] + " " + content_raw)

        # 새 글이면 요약은 항상 수행 (동일 게시글에 대해서는 summary_cache 로 재사용)
        summary = cache_manager.get_summary(cache_key)
        if summary is None:
            summary = summarizer_service.summarize(content_raw)
            # 요약 실패 표시가 없는 경우에만 캐시 (실패 시 다음 subscription에서 재시도)
            if "[요약 생성 실패]" not in summary:
                cache_manager.set_summary(cache_key, summary)
                print(f"[Sub {sub['id']}] 요약 캐시 저장: {cache_key}")
            else:
                print(f"[Sub {sub['id']}] 요약 실패, 캐시 안함: {cache_key}")
        else:
            print(f"[Sub {sub['id']}] 요약 캐시 히트: {cache_key}")

        # 어떤 글이 어떤 요약으로 DB에 들어가는지 눈으로 확인할 수 있게 로그 출력
        print(f"\n[Sub {sub['id']}] 요약 대상 게시글: {latest_post['title']}")
        print(f"[Sub {sub['id']}] 요약 본문 (앞 300자): {summary[:300]}")

        # 알림 생성 요청 데이터 생성 (메타데이터를 모두 포함)
        alert_payload = {
            "user_id": sub["user_id"],
            "subscription_id": sub["id"],
            "site_alias": sub.get("site_alias"),
            "site_post_id": latest_post["id"],
            "title": latest_post["title"],
            "url": latest_post["url"],
            "published_at": latest_post.get("date"),
            "content_raw": content_raw,     # 원문 전체 텍스트
            "content_summary": summary,     # 요약 텍스트
            "keyword_matched": matched,
        }

        alert_service.create_alert(alert_payload)
        alert_service.update_subscription_last_seen(sub["id"], latest_id)
        return

    new_posts = filter_new_posts(posts, last_seen_id)

    if not new_posts: 
        print(f"[Sub {sub['id']}] 새 게시물 없음")
        return

    print(f"[Sub {sub['id']}] 새 게시물 {len(new_posts)}개")
    # 디버깅: 새 게시물 ID 목록 출력
    new_post_ids = [p["id"] for p in new_posts]
    print(f"[Sub {sub['id']}] 🔍 새 게시물 ID: {new_post_ids}")

    for post in new_posts:  # 새로 올라온 게시물들(여러 개일 수도 있음)을 하나씩 순회.
        cache_key = post.get("id") or post["url"]
        if not cache_key:
            print(f"[Sub {sub['id']}] 캐시 키가 없어 스킵합니다: {post['url']}")
            continue
        
        # 캐시에서 본문 가져오기
        content_raw = cache_manager.get_content(cache_key)
        if content_raw is None:
            content_raw = crawler.fetch_post_content(post["url"])
            cache_manager.set_content(cache_key, content_raw)

        # 본문이 비어있으면 이 게시글은 스킵 (하지만 last_seen_id는 업데이트)
        if not content_raw.strip():
            print(f"[Sub {sub['id']}] 본문이 비어있어 스킵합니다: {post['url']}")
            continue

        # 키워드 매칭 여부 (있으면 포함 여부, 없으면 False)
        matched = keyword_match(sub.get("keyword"), post["title"] + " " + content_raw)

        # 새 글이면 요약은 항상 수행 (동일 게시글에 대해서는 summary_cache 로 재사용)
        summary = cache_manager.get_summary(cache_key)
        if summary is None:
            summary = summarizer_service.summarize(content_raw)
            # 요약 실패 표시가 없는 경우에만 캐시 (실패 시 다음 subscription에서 재시도)
            if "[요약 생성 실패]" not in summary:
                cache_manager.set_summary(cache_key, summary)
                print(f"[Sub {sub['id']}] 요약 캐시 저장: {cache_key}")
            else:
                print(f"[Sub {sub['id']}] 요약 실패, 캐시 안함: {cache_key}")
        else:
            print(f"[Sub {sub['id']}] 요약 캐시 히트: {cache_key}")

        # 어떤 글이 어떤 요약으로 DB에 들어가는지 눈으로 확인할 수 있게 로그 출력
        print(f"\n[Sub {sub['id']}] 요약 대상 게시글: {post['title']}")
        print(f"[Sub {sub['id']}] 요약 본문 (앞 300자): {summary[:300]}")

        # 알림 생성 요청 데이터 생성 (메타데이터를 모두 포함)
        alert_payload = {
            "user_id": sub["user_id"],
            "subscription_id": sub["id"],
            "site_alias": sub.get("site_alias"),
            "site_post_id": post["id"],
            "title": post["title"],
            "url": post["url"],
            "published_at": post.get("date"),
            "content_raw": content_raw,     # 원문 전체 텍스트
            "content_summary": summary,     # 요약 텍스트
            "keyword_matched": matched,
        }

        # 키워드 유무/매칭과 상관없이 항상 요약 + 알림 생성
        # (keyword_matched 플래그는 서버/프론트에서 필터링·우선순위용으로 사용 가능)
        alert_service.create_alert(alert_payload)

    # 마지막으로 last_seen_post_id 갱신
    alert_service.update_subscription_last_seen(sub["id"], latest_id)
