import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict
import re
from .base import SiteCrawler

BASE_URL = "https://cse.dongguk.edu"


class DonggukCseNoticeCrawler(SiteCrawler):
    """
    동국대학교 컴퓨터·AI학부 공지사항 크롤러
    예시: https://cse.dongguk.edu/article/notice/list
    
    주의: 상단에 공지사항이 고정되어 있고, 그 다음에 일반 게시글이 나옴
    """
    
    def fetch_post_list(self, list_url: str) -> List[Dict]:
        """
        공지사항 목록 페이지에서 게시물 목록을 가져온다.
        공지사항은 스킵하고 일반 게시글만 반환한다.
        """
        res = requests.get(list_url, timeout=10)
        res.raise_for_status()
        res.encoding = res.apparent_encoding

        soup = BeautifulSoup(res.text, "html.parser")
        html_text = res.text
        
        posts: List[Dict] = []
        seen_ids = set()
        
        # goDetail() 함수 호출에서 게시글 ID 추출 (가장 정확한 방법)
        go_detail_pattern = r'goDetail\((\d+)\)'
        post_ids = list(set(re.findall(go_detail_pattern, html_text)))
        
        for post_id in post_ids:
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)
            
            # goDetail() 호출이 있는 요소 찾기
            go_detail_elem = soup.find(attrs={"onclick": re.compile(rf'goDetail\({post_id}\)')})
            if not go_detail_elem:
                continue
            
            # 부모 요소에서 제목과 날짜 추출
            parent = go_detail_elem.find_parent(["li", "div", "article", "tr"])
            if not parent:
                continue
            
            # 제목 추출
            title = ""
            title_elem = parent.find("a")
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                # 부모 텍스트에서 제목 추출
                parent_text = parent.get_text("\n", strip=True)
                lines = [l.strip() for l in parent_text.split("\n") if l.strip()]
                for line in lines:
                    if (len(line) > 10 and 
                        not re.match(r'^\d{4}-\d{2}-\d{2}', line) and 
                        not re.match(r'^\d+$', line) and
                        "AI융합 관리자" not in line and 
                        "조회수" not in line):
                        title = line
                        break
            
            # 날짜 추출
            date_text = ""
            parent_text = parent.get_text()
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", parent_text)
            if date_match:
                date_text = date_match.group(0)
            
            if not title:
                title = f"게시글 {post_id}"
            
            full_url = urljoin(BASE_URL, f"/article/notice/detail/{post_id}")
            
            posts.append({
                "id": post_id,
                "url": full_url,
                "title": title,
                "date": date_text,
            })
        
        # ID 순으로 정렬 (숫자 기준 내림차순 = 최신순)
        posts.sort(key=lambda x: int(x["id"]) if x["id"].isdigit() else 0, reverse=True)
        
        return posts

    def fetch_post_content(self, post_url: str) -> str:
        """
        상세 페이지에서 본문 텍스트를 추출한다.
        """
        try:
            res = requests.get(post_url, timeout=10)
            res.raise_for_status()
        except Exception as e:
            return ""
        
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        content = None

        # 전략 1: div.bottom > div.contents 구조 우선 탐색
        bottom_div = soup.find("div", class_="bottom")
        if bottom_div:
            content = bottom_div.find("div", class_="contents")
        
        # 전략 2: 일반적인 본문 클래스명으로 탐색
        if not content:
            target_classes = ["contents", "view_con", "board_view_con", "article_view", "kboard-content"]
            for class_name in target_classes:
                content = soup.find("div", class_=class_name)
                if content:
                    break

        # 전략 3: 구조 기반 탐색 (제목 형제 찾기)
        if not content:
            h3_title = soup.find("h3")
            if h3_title:
                header_div = h3_title.parent
                # 적절한 부모 요소 찾기
                for _ in range(2):
                    if header_div.name not in ['div', 'section', 'article', 'header']:
                        header_div = header_div.parent
                    else:
                        break
                
                for sibling in header_div.next_siblings:
                    if not hasattr(sibling, 'name') or not sibling.name:
                        continue
                    
                    classes = sibling.get("class", [])
                    class_str = " ".join(classes) if classes else ""
                    
                    # 메타데이터와 첨부파일 영역 스킵
                    if sibling.name == 'ul' or 'info' in class_str or "file" in class_str or "attach" in class_str:
                        continue

                    # 본문 후보 발견
                    text = sibling.get_text(strip=True)
                    if len(text) > 10 or sibling.find("img"):
                        content = sibling
                        break

        if content:
            # 스크립트, 스타일 제거
            for script in content(["script", "style"]):
                script.decompose()
            
            return content.get_text("\n", strip=True)
        
        return ""

    def _extract_id_from_href(self, href: str) -> str:
        """
        URL에서 게시물 ID를 추출한다.
        예시: /article/notice/detail/1318 → 1318
        """
        # /article/notice/detail/1318 패턴에서 숫자 추출
        match = re.search(r'/detail/(\d+)', href)
        if match:
            return match.group(1)
        
        # 쿼리 파라미터에서 ID 추출 (폴백)
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        
        for key in ("id", "seq", "no", "article_id", "articleId"):
            if key in qs and qs[key]:
                return qs[key][0]
        
        # path의 마지막 숫자 추출 (폴백)
        match = re.search(r'/(\d+)/?$', parsed.path)
        if match:
            return match.group(1)
        
        # 모두 실패하면 href 전체를 ID로 사용
        return parsed.path + ("?" + parsed.query if parsed.query else "")
