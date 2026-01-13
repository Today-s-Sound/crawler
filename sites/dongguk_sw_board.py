import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict
from .base import SiteCrawler

BASE_URL = "https://sw.dongguk.edu"

class DonggukSwBoardCrawler(SiteCrawler):
    def fetch_post_list(self, list_url: str) -> List[Dict]:
        # 네트워크 이슈로 무한 대기하지 않도록 타임아웃 지정
        res = requests.get(list_url, timeout=5)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            # 예상한 테이블 구조가 아니면 조용히 빈 리스트 반환
            return []

        # tbody 가 없으면 table 자체에서 tr 을 찾도록 폴백
        tbody = table.find("tbody") or table
        rows = tbody.find_all("tr")

        posts: List[Dict] = []
        for row in rows:
            a = row.find("a")
            if not a:
                continue

            tds = row.find_all("td")
            # td 개수가 충분하지 않으면 스킵 (구조 변화 대비)
            if len(tds) < 2:
                continue

            # 첫 번째 칸(번호)이 "공지" 인 상단 고정 공지는 스킵
            number_text = tds[0].get_text(strip=True)
            if number_text == "공지":
                continue

            href = a["href"]
            url = urljoin(BASE_URL, href)
            title = a.get_text(strip=True)

            # 실제 HTML 구조 기준으로 뒤에서 두 번째 칸을 날짜로 사용
            date_text = tds[-2].get_text(strip=True)

            post_id = self._extract_id_from_href(href)

            posts.append({
                "id": post_id,
                "url": url,
                "title": title,
                "date": date_text,
            })

        return posts

    def fetch_post_content(self, post_url: str) -> str:
        # 상세 페이지도 타임아웃을 지정해서 안전하게 호출
        res = requests.get(post_url, timeout=5)
        res.raise_for_status()
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        # 실제 HTML 구조에 맞게 class 이름 조정 (하이픈 주의!)
        content = (
            soup.find("div", class_="board-view")  # 동국대 SW교육원 본문 영역 (하이픈!)
            or soup.find("div", class_="board_view")
            or soup.find("div", class_="content")
        )
        
        # 본문을 못 찾으면 빈 문자열 반환 (전체 페이지 반환 방지)
        if content is None:
            print(f"[DonggukSwBoardCrawler] 본문 영역을 찾지 못했습니다: {post_url}")
            return ""
        
        return content.get_text("\n", strip=True)

    # 게시물 ID 추출 하는 로직
    def _extract_id_from_href(self, href: str) -> str:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        # seq, no 같은 파라미터로 ID를 잡고,
        # 없으면 href 전체를 ID처럼 사용
        if "seq" in qs:
            return qs["seq"][0]
        return href