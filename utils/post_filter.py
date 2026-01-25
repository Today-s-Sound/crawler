from typing import List, Dict, Optional


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
