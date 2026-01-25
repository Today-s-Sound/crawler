from containers.application_container import ApplicationContainer
from orchestrators.crawler_orchestrator import CrawlerOrchestrator


def main():
    """
    메인 진입점: DI 컨테이너를 통한 의존성 조립 및 Orchestrator 실행
    """
    # DI 컨테이너 초기화
    container = ApplicationContainer()
    
    # Orchestrator 생성 (의존성 자동 주입)
    orchestrator = CrawlerOrchestrator(
        crawler_factory=container.crawler_factory(),
        alert_service=container.alert_service(),
        summarizer_service=container.summarizer_service(),
    )
    
    # 구독 목록 가져오기
    subscriptions = container.subscription_fetcher()
    
    # Orchestrator를 통해 구독 처리
    orchestrator.process_subscriptions(subscriptions)

if __name__ == "__main__":
    main()

