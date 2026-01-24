import re
import time
from typing import List, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from .base import SiteCrawler


BASE_URL = "https://www.kead.or.kr"


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


class KeadNoticeCrawler(SiteCrawler):
    """
    한국장애인고용공단 부서공지사항 크롤러
    예시: https://www.kead.or.kr/bbs/deptgongji/bbsPage.do?menuId=MENU0895
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
            print(f"[KeadNoticeCrawler] SSL 에러 발생: {list_url}")
            print(f"[KeadNoticeCrawler] 재시도 후에도 실패: {e}")
            return []  # 빈 리스트 반환하여 크롤러 계속 진행
        except requests.exceptions.RequestException as e:
            print(f"[KeadNoticeCrawler] 요청 실패: {list_url}")
            print(f"[KeadNoticeCrawler] 에러: {e}")
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        # 게시판 테이블 찾기
        table = soup.find("table")
        if not table:
            return []

        # tbody가 있으면 tbody에서, 없으면 table에서 직접 tr 찾기
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")

        posts: List[Dict] = []
        for row in rows:
            # a 태그 찾기 (view_link 클래스를 가진 링크가 실제 게시물 링크)
            a = row.find("a", class_="view_link") or row.find("a")
            if not a:
                continue

            title = a.get_text(strip=True)
            if not title:
                continue

            # href 속성 확인
            href = a.get("href", "")
            
            # onclick 속성에서 게시물 ID 추출 (KEAD 사이트는 onclick="fn_bbsView('210496')" 형식)
            post_id = None
            onclick = a.get("onclick", "")
            if onclick:
                # onclick="javascript:fn_bbsView('210496');" 또는 onclick="fn_bbsView('210496')" 패턴
                id_match = re.search(r"fn_bbsView\(['\"]?(\d+)['\"]?\)", onclick)
                if id_match:
                    post_id = id_match.group(1)
                    # 목록 URL에서 menuId와 bbsCode 추출
                    parsed_list_url = urlparse(list_url)
                    list_qs = parse_qs(parsed_list_url.query)
                    menu_id = list_qs.get("menuId", [""])[0]
                    
                    # bbsCode는 URL 경로에서 추출 (/bbs/deptgongji/bbsPage.do)
                    path_parts = parsed_list_url.path.split("/")
                    bbs_code = path_parts[2] if len(path_parts) > 2 else "deptgongji"  # 기본값
                    
                    # 실제 상세 페이지 URL 생성
                    # /bbs/deptgongji/bbsView.do?bbsCnId=210496&menuId=MENU0895 형식
                    if menu_id:
                        href = f"/bbs/{bbs_code}/bbsView.do?bbsCnId={post_id}&menuId={menu_id}"
                    else:
                        href = f"/bbs/{bbs_code}/bbsView.do?bbsCnId={post_id}"

            # href가 유효하지 않으면 스킵
            if not href or href.startswith("javascript:") or href == "#" or href == "void(0);":
                if not post_id:
                    continue
                # post_id가 있으면 URL 생성
                parsed_list_url = urlparse(list_url)
                list_qs = parse_qs(parsed_list_url.query)
                menu_id = list_qs.get("menuId", [""])[0]
                path_parts = parsed_list_url.path.split("/")
                bbs_code = path_parts[2] if len(path_parts) > 2 else "deptgongji"
                if menu_id:
                    href = f"/bbs/{bbs_code}/bbsView.do?bbsCnId={post_id}&menuId={menu_id}"
                else:
                    href = f"/bbs/{bbs_code}/bbsView.do?bbsCnId={post_id}"

            # 상대 경로를 절대 경로로 변환
            url = urljoin(BASE_URL, href)

            # 테이블 구조에서 날짜 추출
            tds = row.find_all("td")
            date_text = ""
            if len(tds) >= 2:
                # 날짜는 보통 마지막에서 두 번째 또는 세 번째 td
                for td in reversed(tds):
                    td_text = td.get_text(strip=True)
                    # YYYY-MM-DD 형식 찾기
                    m = re.search(r"\d{4}-\d{2}-\d{2}", td_text)
                    if m:
                        date_text = m.group(0)
                        break

            # 게시물 ID가 없으면 URL에서 추출
            if not post_id:
                post_id = self._extract_id_from_href(href)

            posts.append({
                "id": post_id,
                "url": url,
                "title": title,
                "date": date_text,
            })

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
            print(f"[KeadNoticeCrawler] SSL 에러 발생: {post_url}")
            print(f"[KeadNoticeCrawler] 재시도 후에도 실패: {e}")
            return ""  # 빈 문자열 반환하여 이 게시글은 스킵
        except requests.exceptions.RequestException as e:
            print(f"[KeadNoticeCrawler] 요청 실패: {post_url}")
            print(f"[KeadNoticeCrawler] 에러: {e}")
            return ""

        soup = BeautifulSoup(res.text, "html.parser")

        # 본문 영역 찾기 (여러 후보 시도)
        content = (
            soup.find("div", class_="board-view")
            or soup.find("div", class_="board_view")
            or soup.find("div", class_="view-content")
            or soup.find("div", class_="view_content")
            or soup.find("div", id="view-content")
            or soup.find("div", id="viewContent")
            or soup.find("div", class_="content")
            or soup.find("div", class_="bbs-content")
            or soup.find("article")
            or soup.find("main")
            or soup.find("section")
        )

        # 본문을 못 찾으면 빈 문자열 반환 (전체 페이지 반환 방지)
        if content is None:
            print(f"[KeadNoticeCrawler] 본문 영역을 찾지 못했습니다: {post_url}")
            # 디버깅: HTML 일부 출력
            print(f"[KeadNoticeCrawler] HTML 샘플 (처음 500자): {soup.get_text()[:500]}")
            return ""

        return content.get_text("\n", strip=True)

    def _extract_id_from_href(self, href: str) -> str:
        """
        URL에서 게시물 ID를 추출한다.
        쿼리 파라미터에서 bbsCnId, nttId, bbsId, seq 등을 찾거나, 없으면 href 전체를 사용
        """
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)

        # KEAD 사이트는 bbsCnId를 사용
        for key in ("bbsCnId", "nttId", "bbsId", "seq", "id", "articleId", "article_id"):
            if key in qs and qs[key]:
                return qs[key][0]

        # 쿼리 파라미터가 없다면 path+query 전체를 fallback ID로 사용
        return parsed.path + ("?" + parsed.query if parsed.query else "")

