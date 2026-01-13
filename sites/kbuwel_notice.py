import re
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import SiteCrawler


BASE_URL = "https://web.kbuwel.or.kr"


class KbuwelNoticeCrawler(SiteCrawler):
    """
    한국시각장애인연합회 '넓은마을' 최근 공지사항 크롤러
    예시: https://web.kbuwel.or.kr/home/notice?next=/
    """

    def fetch_post_list(self, list_url: str) -> List[Dict]:
        res = requests.get(list_url)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")

        # "최근 공지사항" 제목 아래의 리스트 영역을 찾는다.
        header = soup.find(["h2", "h3"], string=lambda s: s and "최근 공지사항" in s)
        if header:
            container = header.find_next("ul") or header.find_next("div")
        else:
            # 구조가 달라졌을 경우를 대비한 폴백: 페이지 내 첫 번째 ul 사용
            container = soup.find("ul")

        if not container:
            return []

        items = container.find_all("li", recursive=False) or container.find_all("li")

        posts: List[Dict] = []
        for item in items:
            a = item.find("a")
            if not a or not a.get("href"):
                continue

            href = a["href"]
            url = urljoin(BASE_URL, href)
            title = a.get_text(strip=True)

            # li 전체 텍스트에서 날짜(YYYY-MM-DD)를 추출
            meta_text = item.get_text(" ", strip=True)
            m = re.search(r"\d{4}-\d{2}-\d{2}", meta_text)
            date_text = m.group(0) if m else ""

            # href 전체를 ID로 사용 (사이트 구조에 맞게 나중에 조정 가능)
            post_id = href

            posts.append(
                {
                    "id": post_id,
                    "url": url,
                    "title": title,
                    "date": date_text,
                }
            )

        # 사이트가 최신→오래된 순으로 내려준다고 가정
        return posts

    def fetch_post_content(self, post_url: str) -> str:
        """
        상세 페이지에서 본문 텍스트를 최대한 깨끗하게 추출한다.
        (구조 변화에 강하도록 main/article/section 등을 우선 탐색)
        """
        res = requests.get(post_url)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")

        # 접근성 사이트 특성상 main / article / section 중 하나에 본문이 있을 가능성이 큼
        content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("section")
        )

        # 본문을 못 찾으면 빈 문자열 반환 (전체 페이지 반환 방지)
        if content is None:
            print(f"[KbuwelNoticeCrawler] 본문 영역을 찾지 못했습니다: {post_url}")
            return ""

        return content.get_text("\n", strip=True)


