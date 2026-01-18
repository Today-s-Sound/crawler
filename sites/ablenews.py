import re
import time
from typing import List, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from .base import SiteCrawler


BASE_URL = "https://www.ablenews.co.kr"


def _create_session():
    """
    재시도 로직과 User-Agent가 포함된 세션 생성
    """
    session = requests.Session()
    
    # 재시도 전략: SSL 에러, 연결 에러 등에 대해 최대 3번 재시도
    retry_strategy = Retry(
        total=3,  # 최대 3번 재시도
        backoff_factor=1,  # 1초, 2초, 4초 대기
        status_forcelist=[429, 500, 502, 503, 504],  # 이 HTTP 상태 코드에 대해 재시도
        allowed_methods=["GET"],  # GET 요청만 재시도
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # User-Agent 설정 (일반 브라우저처럼 보이게)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    return session


class AbleNewsCrawler(SiteCrawler):
    """
    에이블뉴스 전체기사/섹션 기사 목록 크롤러

    예시: https://www.ablenews.co.kr/news/articleList.html?view_type=sm
    """

    def fetch_post_list(self, list_url: str) -> List[Dict]:
        try:
            session = _create_session()
            res = session.get(list_url, timeout=10)
            res.raise_for_status()
            res.encoding = res.apparent_encoding
        except requests.exceptions.SSLError as e:
            print(f"[AbleNewsCrawler] SSL 에러 발생: {list_url}")
            print(f"[AbleNewsCrawler] 재시도 후에도 실패: {e}")
            return []  # 빈 리스트 반환하여 크롤러 계속 진행
        except requests.exceptions.RequestException as e:
            print(f"[AbleNewsCrawler] 요청 실패: {list_url}")
            print(f"[AbleNewsCrawler] 에러: {e}")
            return []

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
        try:
            session = _create_session()
            time.sleep(0.5)  # 요청 간 0.5초 대기 (서버 부담 감소)
            res = session.get(post_url, timeout=10)
            res.raise_for_status()
            res.encoding = res.apparent_encoding
        except requests.exceptions.SSLError as e:
            print(f"[AbleNewsCrawler] SSL 에러 발생: {post_url}")
            print(f"[AbleNewsCrawler] 재시도 후에도 실패: {e}")
            return ""  # 빈 문자열 반환하여 이 게시글은 스킵
        except requests.exceptions.RequestException as e:
            print(f"[AbleNewsCrawler] 요청 실패: {post_url}")
            print(f"[AbleNewsCrawler] 에러: {e}")
            return ""

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
