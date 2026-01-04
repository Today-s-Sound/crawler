# test_ablenews.py
from sites.ablenews import AbleNewsCrawler

LIST_URL = "https://www.ablenews.co.kr/news/articleList.html?view_type=sm"

def main():
    crawler = AbleNewsCrawler()

    print("[TEST] 목록 크롤링 시작...")
    posts = crawler.fetch_post_list(LIST_URL)
    print(f"[TEST] 게시글 개수: {len(posts)}")
    for p in posts[:5]:
        print(p)

    if not posts:
        return

    first = posts[0]
    print("\n[TEST] 첫 게시글 메타데이터:", first)

    print("\n[TEST] 첫 게시글 본문(앞 500자):")
    content = crawler.fetch_post_content(first["url"])
    print(content[:500])

if __name__ == "__main__":
    main()