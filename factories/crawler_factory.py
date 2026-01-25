from typing import Dict, Type
from urllib.parse import urlparse

from sites.base import SiteCrawler
from sites.dongguk_sw_board import DonggukSwBoardCrawler
from sites.dongguk_cse_notice import DonggukCseNoticeCrawler
from sites.kbuwel_notice import KbuwelNoticeCrawler
from sites.ablenews import AbleNewsCrawler
from sites.kead_notice import KeadNoticeCrawler
from sites.silwel_notice import SilwelNoticeCrawler
from sites.koddi_notice import KoddiNoticeCrawler


class CrawlerFactory:
    """
    크롤러 생성 책임을 캡슐화하는 Factory 클래스
    - 새 크롤러 추가 시 register()만 호출하면 됨 (OCP 준수)
    """
    
    _registry: Dict[str, Type[SiteCrawler]] = {}
    
    # URL 도메인 → 크롤러 타입 매핑
    _domain_mapping = {
        "sw.dongguk.edu": "DONGGUK_SW",
        "cse.dongguk.edu": "DONGGUK_CSE",
        "web.kbuwel.or.kr": "KBUWEL",
        "ablenews.co.kr": "ABLE_NEWS",
        "kead.or.kr": "KEAD",
        "silwel.or.kr": "SILWEL",
        "koddi.or.kr": "KODDI",
    }
    
    @classmethod
    def _initialize_registry(cls):
        """기본 크롤러들을 레지스트리에 등록"""
        if cls._registry:
            return  # 이미 초기화됨
        
        cls.register("DONGGUK_SW", DonggukSwBoardCrawler)
        cls.register("DONGGUK_CSE", DonggukCseNoticeCrawler)
        cls.register("KBUWEL", KbuwelNoticeCrawler)
        cls.register("ABLE_NEWS", AbleNewsCrawler)
        cls.register("KEAD", KeadNoticeCrawler)
        cls.register("SILWEL", SilwelNoticeCrawler)
        cls.register("KODDI", KoddiNoticeCrawler)
    
    @classmethod
    def register(cls, site_type: str, crawler_class: Type[SiteCrawler]):
        """
        크롤러를 레지스트리에 등록
        
        Args:
            site_type: 사이트 타입 식별자 (예: "DONGGUK_SW")
            crawler_class: 크롤러 클래스
        """
        cls._registry[site_type] = crawler_class
    
    @classmethod
    def create(cls, subscription: Dict) -> SiteCrawler:
        """
        구독 정보로부터 적절한 크롤러를 생성
        
        Args:
            subscription: 구독 정보 딕셔너리 (site_type, site_url 포함)
            
        Returns:
            SiteCrawler 인스턴스
        """
        cls._initialize_registry()
        
        # 방법 1: site_type으로 직접 선택
        site_type = subscription.get("site_type")
        if site_type and site_type in cls._registry:
            crawler_class = cls._registry[site_type]
            return crawler_class()
        
        # 방법 2: URL 도메인으로 추론
        site_url = subscription.get("site_url", "")
        if site_url:
            host = urlparse(site_url).netloc
            for domain, crawler_type in cls._domain_mapping.items():
                if domain in host:
                    crawler_class = cls._registry[crawler_type]
                    return crawler_class()
        
        # 기본값: 동국대 SW 크롤러 (하위 호환성)
        print(f"[CrawlerFactory] ⚠️ 크롤러를 찾지 못해 기본값(DonggukSwBoardCrawler) 사용: {subscription.get('site_url', 'unknown')}")
        return DonggukSwBoardCrawler()
    
    @classmethod
    def get_registered_types(cls) -> list[str]:
        """등록된 크롤러 타입 목록 반환"""
        cls._initialize_registry()
        return list(cls._registry.keys())
