from dependency_injector import containers, providers

from services.alert_service import DefaultAlertService
from services.summarizer_service import DefaultSummarizerService
from services.cache_manager import CacheManager
from services.subscription_client import fetch_subscriptions
from factories.crawler_factory import CrawlerFactory


class ApplicationContainer(containers.DeclarativeContainer):
    """
    애플리케이션 의존성 주입 컨테이너
    - 모든 서비스와 팩토리의 생명주기를 관리
    - 테스트 시 Mock 객체로 쉽게 교체 가능
    """
    
    # 서비스들 (Singleton으로 한 번만 생성)
    alert_service = providers.Singleton(DefaultAlertService)
    summarizer_service = providers.Singleton(DefaultSummarizerService)
    
    # 캐시 매니저 (Factory로 매번 새로 생성 - 사이트별로 독립적)
    cache_manager = providers.Factory(CacheManager)
    
    # 크롤러 팩토리 (Singleton)
    crawler_factory = providers.Singleton(CrawlerFactory)
    
    # 구독 목록 가져오기 함수 (Function provider)
    subscription_fetcher = providers.Callable(fetch_subscriptions)
