# test_dongguk_sw.py
from sites.dongguk_sw_board import DonggukSwBoardCrawler
from services.summarizer import summarize  # 요약까지 같이 확인하고 싶으면

LIST_URL = "https://sw.dongguk.edu/board/list.do?id=S181"

def main():
    crawler = DonggukSwBoardCrawler()

    print("[DONGGUK TEST] 목록 크롤링 시작...")
    posts = crawler.fetch_post_list(LIST_URL)
    print(f"[DONGGUK TEST] 게시글 개수: {len(posts)}")
    for p in posts[:5]:
        print(p)

    if not posts:
        return

    latest = posts[0]
    print("\n[DONGGUK TEST] 최신 게시글 메타데이터:", latest)

    content = crawler.fetch_post_content(latest["url"])
    print("\n[DONGGUK TEST] 최신 게시글 본문 (앞 500자):")
    print(content[:500])

    # 요약까지 테스트
    summary = summarize(content)
    print("\n[DONGGUK TEST] 요약 결과 (앞 300자):")
    print(summary[:300])

if __name__ == "__main__":
    main()