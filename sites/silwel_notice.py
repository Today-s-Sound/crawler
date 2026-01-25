import re
import time
from typing import List, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from .base import SiteCrawler


BASE_URL = "https://www.silwel.or.kr"


def _create_session():
    """
    재시도 로직과 User-Agent가 포함된 세션 생성
    """
    session = requests.Session()
    
    # 재시도 전략: SSL 에러, 연결 에러 등에 대해 최대 3번 재시도
    retry_strategy = Retry(
        total=3,  # 최대 3번 재시도
        backoff_factor=1,  # 1초, 2초, 4초 대기
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # User-Agent 설정 (일반 브라우저처럼 보이게)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    return session


class SilwelNoticeCrawler(SiteCrawler):
    """
    실로암시각장애인복지관 공지사항 크롤러
    예시: https://www.silwel.or.kr/v2/modules/board/board.php?tbl=board_comm_notice
    """

    def fetch_post_list(self, list_url: str) -> List[Dict]:
        """
        공지사항 목록 페이지에서 게시물 목록을 가져온다.
        """
        try:
            session = _create_session()
            res = session.get(list_url, timeout=10)
            res.raise_for_status()
            res.encoding = res.apparent_encoding
        except requests.exceptions.SSLError as e:
            print(f"[SilwelNoticeCrawler] SSL 에러 발생: {list_url}")
            print(f"[SilwelNoticeCrawler] 재시도 후에도 실패: {e}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"[SilwelNoticeCrawler] 요청 실패: {list_url}")
            print(f"[SilwelNoticeCrawler] 에러: {e}")
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # 게시판 테이블 찾기
        table = soup.find("table")
        if not table:
            print(f"[SilwelNoticeCrawler] 테이블을 찾지 못했습니다: {list_url}")
            return []

        # tbody가 있으면 tbody에서, 없으면 table에서 직접 tr 찾기
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")

        posts: List[Dict] = []
        for row in rows:
            # 헤더 행 스킵 (th 태그가 있으면 헤더)
            if row.find("th"):
                continue

            # a 태그 찾기 (제목 링크)
            a = row.find("a")
            if not a or not a.get("href"):
                continue

            href = a.get("href", "")
            title = a.get_text(strip=True)
            
            if not title:
                continue

            # 목록 페이지 URL을 기준으로 변환
            # 예: https://www.silwel.or.kr/v2/modules/board/board.php?tbl=...
            #    + ./board_view.php?tbl=...
            #    = https://www.silwel.or.kr/v2/modules/board/board_view.php?tbl=...
            url = urljoin(list_url, href)

            # URL에서 게시글 ID 추출
            post_id = self._extract_id_from_href(href)

            # 테이블 구조에서 날짜 추출
            tds = row.find_all("td")
            date_text = ""
            if len(tds) >= 4:  # 번호, 제목, 첨부, 작성자, 작성일, 조회
                # 작성일은 보통 뒤에서 두 번째 또는 세 번째 td
                for td in reversed(tds):
                    td_text = td.get_text(strip=True)
                    # YYYY-MM-DD 형식 찾기
                    m = re.search(r"\d{4}-\d{2}-\d{2}", td_text)
                    if m:
                        date_text = m.group(0)
                        break

            posts.append({
                "id": post_id,
                "url": url,
                "title": title,
                "date": date_text,
            })

        # 사이트가 최신→오래된 순으로 내려준다고 가정
        return posts

    def fetch_post_content(self, post_url: str) -> str:
        """
        상세 페이지에서 본문 텍스트를 최대한 깨끗하게 추출한다.
        """
        try:
            session = _create_session()
            time.sleep(0.5)  # 요청 간 0.5초 대기 (서버 부담 감소)
            res = session.get(post_url, timeout=10)
            res.raise_for_status()
            res.encoding = res.apparent_encoding
        except requests.exceptions.SSLError as e:
            print(f"[SilwelNoticeCrawler] SSL 에러 발생: {post_url}")
            print(f"[SilwelNoticeCrawler] 재시도 후에도 실패: {e}")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"[SilwelNoticeCrawler] 요청 실패: {post_url}")
            print(f"[SilwelNoticeCrawler] 에러: {e}")
            return ""

        soup = BeautifulSoup(res.text, "html.parser")

        # 실로암 사이트는 본문이 테이블 구조로 되어 있음
        # "공지사항" 제목 아래의 테이블에서 본문 추출
        content = None
        
        # 방법 1: "공지사항" 제목 아래의 테이블 찾기
        h1_title = soup.find("h1", string=lambda s: s and "공지사항" in s)
        if h1_title:
            # h1 다음에 오는 테이블 찾기
            table = h1_title.find_next("table")
            if table:
                # 테이블의 모든 텍스트 추출
                content = table
        
        # 방법 2: 일반적인 div 구조 시도
        if not content:
            content = (
                soup.find("div", class_="board-view")
                or soup.find("div", class_="board_view")
                or soup.find("div", class_="view-content")
                or soup.find("div", class_="view_content")
                or soup.find("div", id="view-content")
                or soup.find("div", id="viewContent")
                or soup.find("div", class_="content")
                or soup.find("div", class_="bbs-content")
            )
        
        # 방법 3: 페이지 내 모든 테이블 중 본문이 있을 가능성이 높은 테이블 찾기
        if not content:
            all_tables = soup.find_all("table")
            for table in all_tables:
                table_text = table.get_text(strip=True)
                
                # "등록일", "조회수", "첨부파일" 같은 메타데이터가 있으면 본문일 가능성 높음
                # 메타데이터가 있으면 길이와 상관없이 본문으로 판단
                has_metadata = any(keyword in table_text for keyword in ["등록일", "조회수", "첨부파일", "작성일", "작성자"])
                
                if has_metadata:
                    # 메타데이터가 있으면 본문일 가능성이 매우 높음 (길이 제한 없음)
                    content = table
                    break
                elif len(table_text) > 50:  # 메타데이터가 없어도 50자 이상이면 본문일 가능성
                    # 하지만 메타데이터가 있는 테이블을 우선 찾기 위해 계속 탐색
                    if not content:  # 아직 본문을 찾지 못했으면 임시로 저장
                        content = table

        # 본문을 못 찾으면 빈 문자열 반환 (전체 페이지 반환 방지)
        if content is None:
            print(f"[SilwelNoticeCrawler] 본문 영역을 찾지 못했습니다: {post_url}")
            # 디버깅: HTML 일부 출력
            print(f"[SilwelNoticeCrawler] HTML 샘플 (처음 500자): {soup.get_text()[:500]}")
            return ""

        # 테이블인 경우, 헤더 행(th)과 불필요한 요소 제거
        text_parts = []
        if content.name == "table":
            rows = content.find_all("tr")
            for row in rows:
                # 헤더 행 스킵
                if row.find("th"):
                    continue
                # 각 셀의 텍스트 추출
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if cell_text and len(cell_text) > 5:  # 너무 짧은 텍스트는 스킵
                        text_parts.append(cell_text)
            return "\n".join(text_parts)
        else:
            return content.get_text("\n", strip=True)

    def _extract_id_from_href(self, href: str) -> str:
        """
        URL에서 게시물 ID를 추출한다.
        실로암 사이트는 board_view.php?tbl=board_comm_notice&id=10363 형식
        """
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)

        # id 파라미터 사용
        for key in ("id", "bbsCnId", "nttId", "bbsId", "seq", "articleId", "article_id"):
            if key in qs and qs[key]:
                return qs[key][0]

        # 쿼리 파라미터가 없다면 path+query 전체를 fallback ID로 사용
        return parsed.path + ("?" + parsed.query if parsed.query else "")
