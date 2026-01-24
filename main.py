import os
from typing import List, Dict, Optional
from urllib.parse import urlparse

from sites.dongguk_sw_board import DonggukSwBoardCrawler
from sites.kbuwel_notice import KbuwelNoticeCrawler
from sites.ablenews import AbleNewsCrawler
from sites.kead_notice import KeadNoticeCrawler
from sites.silwel_notice import SilwelNoticeCrawler
from services.subscription_client import fetch_subscriptions
from services.notification_client import create_alert, update_subscription_last_seen
from services.summarizer import summarize


def filter_new_posts(posts: List[Dict], last_seen_post_id: Optional[str]) -> List[Dict]:
    """
    posts: 최신→오래된 순
    last_seen_post_id: None이면 '새로 본 게 없다'고 가정하고, 이번에는 새 알림 안 만듦.
    return: 지난번 이후 새로 올라온 게시물들 (오래된→최신 순)
    
    안전 장치:
    - last_seen_post_id가 현재 페이지에 없으면 두 가지 경우:
      1) last_seen_post_id가 현재 게시글들보다 최신 → 0개 반환 (게시글 삭제/공지 전환)
      2) last_seen_post_id가 현재 게시글들보다 오래됨 → 최신 3개만 반환 (페이지 넘어감)
    """
    if last_seen_post_id is None:
        return []

    if not posts:
        return []

    # 디버깅: 현재 페이지의 모든 게시글 ID 출력
    post_ids = [p["id"] for p in posts]
    print(f"[filter_new_posts] 🔍 현재 페이지 게시글 ID: {post_ids[:5]}{'...' if len(post_ids) > 5 else ''}")
    print(f"[filter_new_posts] 🔍 찾고 있는 last_seen_post_id: {last_seen_post_id}")

    new_posts = []
    found = False
    
    for post in posts:
        if post["id"] == last_seen_post_id:
            found = True
            print(f"[filter_new_posts] ✅ last_seen_post_id를 찾았습니다!")
            break
        new_posts.append(post)
    
    # last_seen_post_id를 찾지 못한 경우
    if not found:
        print(f"[filter_new_posts] ⚠️ last_seen_post_id={last_seen_post_id}를 찾지 못했습니다.")
        
        # ID 비교를 통한 판단 (숫자 ID인 경우에만)
        try:
            last_id_num = int(last_seen_post_id)
            latest_id_num = int(posts[0]["id"])
            oldest_id_num = int(posts[-1]["id"])
            
            # last_seen_id가 현재 페이지의 최신 게시글보다 크거나 같음
            # → 게시글이 삭제되었거나 공지로 전환됨
            # → 새 게시글 없음!
            if last_id_num >= latest_id_num:
                print(f"[filter_new_posts] 🔍 last_seen_id({last_id_num}) >= latest_id({latest_id_num})")
                print(f"[filter_new_posts] ✅ 게시글이 삭제되었거나 공지로 전환됨. 새 게시글 없음!")
                return []
            
            # last_seen_id가 현재 페이지의 가장 오래된 게시글보다 작음
            # → 두 번째 페이지로 넘어감
            # → 안전 장치: 최신 3개만 반환
            elif last_id_num < oldest_id_num:
                print(f"[filter_new_posts] 🔍 last_seen_id({last_id_num}) < oldest_id({oldest_id_num})")
                print(f"[filter_new_posts] ⚠️ 게시글이 많이 올라와 페이지가 넘어감. 최신 3개만 반환")
                new_posts = new_posts[:3]
            
        except (ValueError, TypeError):
            # ID가 숫자가 아닌 경우 (URL 등)
            # 보수적으로 최신 3개만 반환
            print(f"[filter_new_posts] ⚠️ ID가 숫자가 아님. 보수적으로 최신 3개만 반환")
            if len(new_posts) > 3:
                new_posts = new_posts[:3]

    new_posts.reverse()
    return new_posts

def keyword_match(keyword: Optional[str], text: str) -> bool:
    """
    키워드가 없으면 False 반환(=매칭 없음).
    키워드가 있으면 단순 포함 여부로 매칭 판단.
    - 요약은 항상 수행하고,
    - "키워드가 있고 + 매칭된 경우"에만 알림을 생성하기 위해 사용.
    """
    if not keyword:
        return False
    return keyword in text  # 간단한 포함 여부 (나중에 개선 가능)


def get_crawler_for_subscription(sub: Dict):
    """
    구독의 site_url(또는 site_type)을 보고 어떤 크롤러를 쓸지 결정.
    - sw.dongguk.edu        → DonggukSwBoardCrawler
    - web.kbuwel.or.kr      → KbuwelNoticeCrawler
    - www.ablenews.co.kr    → AbleNewsCrawler
    - www.kead.or.kr       → KeadNoticeCrawler
    - www.silwel.or.kr     → SilwelNoticeCrawler
    """
    site_type = sub.get("site_type")
    if site_type == "DONGGUK_SW":
        return DonggukSwBoardCrawler()
    if site_type == "KBUWEL":
        return KbuwelNoticeCrawler()
    if site_type == "ABLE_NEWS":
        return AbleNewsCrawler()
    if site_type == "KEAD":
        return KeadNoticeCrawler()
    if site_type == "SILWEL":
        return SilwelNoticeCrawler()

    # site_type 이 없으면 URL 도메인으로 추론
    url = sub.get("site_url", "")
    host = urlparse(url).netloc
    if "sw.dongguk.edu" in host:
        return DonggukSwBoardCrawler()
    if "web.kbuwel.or.kr" in host:
        return KbuwelNoticeCrawler()
    if "ablenews.co.kr" in host:
        return AbleNewsCrawler()
    if "kead.or.kr" in host:
        return KeadNoticeCrawler()
    if "silwel.or.kr" in host:
        return SilwelNoticeCrawler()

    # 기본값: 동국대 크롤러
    return DonggukSwBoardCrawler()


# “구독 하나에 대해 ‘이번 턴에 새로 생긴 알림’을 DB에 쌓는 단위 작업”
def process_subscription(
    sub: Dict,
    crawler,
    posts: List[Dict],
    content_cache: Dict[str, str],
    summary_cache: Dict[str, str],
):
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
            update_subscription_last_seen(sub["id"], latest_id)
            return
        if cache_key in content_cache:
            content_raw = content_cache[cache_key]
        else:
            content_raw = crawler.fetch_post_content(latest_post["url"])
            content_cache[cache_key] = content_raw

        # 본문이 비어있으면 스킵 (크롤러가 본문 영역을 찾지 못한 경우)
        if not content_raw.strip():
            print(f"[Sub {sub['id']}] 본문이 비어있어 스킵합니다: {latest_post['url']}")
            update_subscription_last_seen(sub["id"], latest_id)
            return

        # 키워드 매칭 여부 (있으면 포함 여부, 없으면 False)
        matched = keyword_match(sub.get("keyword"),
                                latest_post["title"] + " " + content_raw)

        # 새 글이면 요약은 항상 수행 (동일 게시글에 대해서는 summary_cache 로 재사용)
        if cache_key in summary_cache:
            summary = summary_cache[cache_key]
            print(f"[Sub {sub['id']}] 요약 캐시 히트: {cache_key}")
        else:
            summary = summarize(content_raw)
            # 요약 실패 표시가 없는 경우에만 캐시 (실패 시 다음 subscription에서 재시도)
            if "[요약 생성 실패]" not in summary:
                summary_cache[cache_key] = summary
                print(f"[Sub {sub['id']}] 요약 캐시 저장: {cache_key}")
            else:
                print(f"[Sub {sub['id']}] 요약 실패, 캐시 안함: {cache_key}")

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

        create_alert(alert_payload)
        update_subscription_last_seen(sub["id"], latest_id)
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
        if cache_key in content_cache:
            content_raw = content_cache[cache_key]
        else:
            content_raw = crawler.fetch_post_content(post["url"])
            content_cache[cache_key] = content_raw

        # 본문이 비어있으면 이 게시글은 스킵 (하지만 last_seen_id는 업데이트)
        if not content_raw.strip():
            print(f"[Sub {sub['id']}] 본문이 비어있어 스킵합니다: {post['url']}")
            continue

        # 키워드 매칭 여부 (있으면 포함 여부, 없으면 False)
        matched = keyword_match(sub.get("keyword"), post["title"] + " " + content_raw)

        # 새 글이면 요약은 항상 수행 (동일 게시글에 대해서는 summary_cache 로 재사용)
        if cache_key in summary_cache:
            summary = summary_cache[cache_key]
            print(f"[Sub {sub['id']}] 요약 캐시 히트: {cache_key}")
        else:
            summary = summarize(content_raw)
            # 요약 실패 표시가 없는 경우에만 캐시 (실패 시 다음 subscription에서 재시도)
            if "[요약 생성 실패]" not in summary:
                summary_cache[cache_key] = summary
                print(f"[Sub {sub['id']}] 요약 캐시 저장: {cache_key}")
            else:
                print(f"[Sub {sub['id']}] 요약 실패, 캐시 안함: {cache_key}")

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
        create_alert(alert_payload)

    # 마지막으로 last_seen_post_id 갱신
    update_subscription_last_seen(sub["id"], latest_id)


def main():
    subs = fetch_subscriptions()
    print(f"총 구독 수: {len(subs)}")

    # site_url 기준으로 구독들을 그룹화해서
    # 같은 사이트는 목록 크롤링을 한 번만 수행하고 결과를 공유한다.
    groups: Dict[str, List[Dict]] = {}
    for sub in subs:
        site_url = sub["site_url"]
        groups.setdefault(site_url, []).append(sub)

    for site_url, site_subs in groups.items():
        # 대표 구독 하나를 기준으로 어떤 크롤러를 쓸지 결정
        rep_sub = site_subs[0]
        crawler = get_crawler_for_subscription(rep_sub)

        print(f"\n[Site] site_url={site_url}, crawler={type(crawler).__name__}, subs={len(site_subs)}")

        # 해당 사이트에 대한 게시글 목록은 한 번만 크롤링
        posts = crawler.fetch_post_list(site_url)
        if not posts:
            print(f"[Site] site_url={site_url} 에서 게시글이 없습니다.")
            continue

        # 상세 본문/요약도 여러 구독에서 공유할 수 있도록 캐시
        content_cache: Dict[str, str] = {}
        summary_cache: Dict[str, str] = {}

        for sub in site_subs:
            try:
                process_subscription(sub, crawler, posts, content_cache, summary_cache)
            except Exception as e:
                sub_id = sub.get('id', 'unknown') if 'sub' in locals() else 'unknown'
                print(f"[Sub {sub_id}] 처리 중 오류: {e}")

if __name__ == "__main__":
    main()

