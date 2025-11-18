import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict
from .base import SiteCrawler

BASE_URL = "https://sw.dongguk.edu"

class DonggukSwBoardCrawler(SiteCrawler):
    def fetch_post_list(self, list_url: str) -> List[Dict]:
        res = requests.get(list_url)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        tbody = table.find("tbody")
        rows = tbody.find_all("tr")

        posts: List[Dict] = []
        for row in rows:
            a = row.find("a")
            if not a:
                continue
            href = a["href"]
            url = urljoin(BASE_URL, href)
            title = a.get_text(strip=True)

            tds = row.find_all("td")
            date_text = tds[-2].get_text(strip=True)  # 실제 HTML 구조 보고 이 인덱스(-2)가 맞는지 꼭 확인

            post_id = self._extract_id_from_href(href)

            posts.append({
                "id": post_id,
                "url": url,
                "title": title,
                "date": date_text,
            })

        return posts

    def fetch_post_content(self, post_url: str) -> str:
        res = requests.get(post_url)
        res.raise_for_status()
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        # 실제 HTML 구조에 맞게 class 이름 조정 필요
        content = (
            soup.find("div", class_="board_view") # 실제로 본문을 감싸는 영역 1트
            or soup.find("div", class_="content") # 실제로 본문을 감싸는 영역 2트
            or soup # 그래도 못 찾았으면 그냥 전체 문서에서 텍스트 뽑아버리기
        )
        return content.get_text("\n", strip=True) # 텍스트를 하나의 문자열로 뽑아내고, 앞뒤 공백은 제거

    # 게시물 ID 추출 하는 로직
    def _extract_id_from_href(self, href: str) -> str:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        # seq, no 같은 파라미터로 ID를 잡고,
        # 없으면 href 전체를 ID처럼 사용
        if "seq" in qs:
            return qs["seq"][0]
        return href