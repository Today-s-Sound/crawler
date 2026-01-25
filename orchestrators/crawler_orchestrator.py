from typing import List, Dict

from services.alert_service import AlertService
from services.summarizer_service import SummarizerService
from services.cache_manager import CacheManager
from factories.crawler_factory import CrawlerFactory
from services.subscription_processor import process_subscription


class CrawlerOrchestrator:
    """
    크롤링 전체 흐름을 조율하는 Orchestrator 클래스
    - 구독 그룹화, 크롤링, 처리 로직을 캡슐화
    - 의존성 주입을 통해 테스트 가능하도록 설계
    """
    
    def __init__(
        self,
        crawler_factory: CrawlerFactory,
        alert_service: AlertService,
        summarizer_service: SummarizerService,
    ):
        """
        Args:
            crawler_factory: 크롤러 생성 팩토리
            alert_service: 알림 서비스
            summarizer_service: 요약 서비스
        """
        self._crawler_factory = crawler_factory
        self._alert_service = alert_service
        self._summarizer_service = summarizer_service
    
    def process_subscriptions(self, subscriptions: List[Dict]) -> None:
        """
        구독 목록을 처리한다.
        
        Args:
            subscriptions: 구독 정보 리스트
        """
        if not subscriptions:
            print("구독이 없습니다.")
            return
        
        print(f"총 구독 수: {len(subscriptions)}")
        
        # site_url 기준으로 구독들을 그룹화
        # 같은 사이트는 목록 크롤링을 한 번만 수행하고 결과를 공유
        groups = self._group_subscriptions_by_site(subscriptions)
        
        for site_url, site_subs in groups.items():
            self._process_site_group(site_url, site_subs)
    
    def _group_subscriptions_by_site(self, subscriptions: List[Dict]) -> Dict[str, List[Dict]]:
        """
        구독들을 site_url 기준으로 그룹화한다.
        
        Args:
            subscriptions: 구독 정보 리스트
            
        Returns:
            site_url을 키로 하는 그룹화된 딕셔너리
        """
        groups: Dict[str, List[Dict]] = {}
        for sub in subscriptions:
            site_url = sub["site_url"]
            groups.setdefault(site_url, []).append(sub)
        return groups
    
    def _process_site_group(self, site_url: str, site_subs: List[Dict]) -> None:
        """
        같은 사이트의 구독들을 처리한다.
        
        Args:
            site_url: 사이트 URL
            site_subs: 해당 사이트의 구독 목록
        """
        # 대표 구독 하나를 기준으로 크롤러 생성
        rep_sub = site_subs[0]
        crawler = self._crawler_factory.create(rep_sub)
        
        print(f"\n[Site] site_url={site_url}, crawler={type(crawler).__name__}, subs={len(site_subs)}")
        
        # 해당 사이트에 대한 게시글 목록은 한 번만 크롤링
        posts = crawler.fetch_post_list(site_url)
        if not posts:
            print(f"[Site] site_url={site_url} 에서 게시글이 없습니다.")
            return
        
        # 캐시 매니저 생성 (사이트별로 독립적인 캐시)
        cache_manager = CacheManager()
        
        # 각 구독 처리
        for sub in site_subs:
            try:
                process_subscription(
                    sub=sub,
                    crawler=crawler,
                    posts=posts,
                    alert_service=self._alert_service,
                    summarizer_service=self._summarizer_service,
                    cache_manager=cache_manager,
                )
            except Exception as e:
                sub_id = sub.get('id', 'unknown')
                print(f"[Sub {sub_id}] 처리 중 오류: {e}")
