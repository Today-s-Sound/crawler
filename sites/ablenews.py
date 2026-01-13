import re
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from .base import SiteCrawler


BASE_URL = "https://www.ablenews.co.kr"


class AbleNewsCrawler(SiteCrawler):
    """
    에이블뉴스 전체기사/섹션 기사 목록 크롤러

    예시: https://www.ablenews.co.kr/news/articleList.html?view_type=sm
    """

    def fetch_post_list(self, list_url: str) -> List[Dict]:
        res = requests.get(list_url)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")

        # 에이블뉴스 기사 상세 URL 패턴: /news/articleView.html?idxno=xxxxx 형태가 많음
        anchors = soup.find_all("a", href=True)

        posts: List[Dict] = []
        seen_ids = set()

        for a in anchors:
            href = a["href"]
            if "articleView" not in href:  # 리스트/광고/기타 링크는 모두 스킵
                continue

            title = a.get_text(strip=True)
            if not title:
                continue

            url = urljoin(BASE_URL, href)
            post_id = self._extract_id_from_href(href)

            # 같은 기사에 대한 중복 링크 제거
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            # 날짜 텍스트 추출
            # - 보통 제목/메타 정보가 같은 li/div 안에 붙어 있으므로,
            #   부모 컨테이너 텍스트에서 날짜 패턴을 regex 로 뽑는다.
            container = a.find_parent(["li", "tr", "article", "div"]) or a
            meta_text = container.get_text(" ", strip=True)

            # 2025-12-19 또는 2025.12.19 형태 모두 허용
            m = re.search(r"\d{4}[.-]\d{2}[.-]\d{2}", meta_text)
            if m:
                raw_date = m.group(0)
                date_text = raw_date.replace(".", "-")
            else:
                date_text = ""

            posts.append(
                {
                    "id": post_id,
                    "url": url,
                    "title": title,
                    "date": date_text,
                }
            )

        # 페이지 상단에 최신 기사가 오도록 이미 정렬되어 있다고 가정하고 그대로 반환
        return posts

    def fetch_post_content(self, post_url: str) -> str:
        """
        기사 상세 페이지에서 본문 텍스트를 최대한 깨끗하게 추출한다.
        """
        res = requests.get(post_url)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")

        # 실제 HTML 구조에 맞게 우선순위를 두고 여러 후보를 탐색
        content = (
            soup.find("div", id="article-view-content-div")
            or soup.find("div", id="articleBody")
            or soup.find("div", class_="article")
            or soup.find("div", class_="article-body")
            or soup.find("div", id="content")
        )

        # 본문을 못 찾으면 빈 문자열 반환 (전체 페이지 반환 방지)
        if content is None:
            print(f"[AbleNewsCrawler] 본문 영역을 찾지 못했습니다: {post_url}")
            return ""

        return content.get_text("\n", strip=True)

    def _extract_id_from_href(self, href: str) -> str:
        """
        /news/articleView.html?idxno=xxxxx 와 같은 구조에서 idxno(또는 article_id)를 ID 로 사용.
        해당 파라미터가 없으면 href 전체를 ID 처럼 사용.
        """
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)

        for key in ("idxno", "article_id", "aid"):
            if key in qs and qs[key]:
                return qs[key][0]

        # 쿼리 파라미터가 없다면 path+query 전체를 fallback ID 로 사용
        return parsed.path + ("?" + parsed.query if parsed.query else "")
