from abc import ABC, abstractmethod
from typing import List, Dict

class SiteCrawler(ABC):
    """
    특정 사이트(예: 동국대 SW게시판)에 대한 크롤링 방법을 정의하는 베이스 클래스
    """

    @abstractmethod
    def fetch_post_list(self, list_url: str) -> List[Dict]:
        """
        리스트 페이지에서 게시물 목록을 가져온다.
        return: [
          {
            "id": "사이트내_게시물_ID",
            "url": "상세페이지_URL",
            "title": "제목",
            "date": "2025-11-14",
          },
          ...
        ]  # 최신→오래된 순
        """
        pass

    @abstractmethod
    def fetch_post_content(self, post_url: str) -> str:
        """
        상세 페이지에서 본문 텍스트를 가져온다.
        """
        pass