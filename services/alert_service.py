from abc import ABC, abstractmethod
from typing import Dict
from services.notification_client import create_alert as _create_alert
from services.notification_client import update_subscription_last_seen as _update

class AlertService(ABC):
    """알림 관련 서비스 인터페이스"""
    
    @abstractmethod
    def create_alert(self, alert: Dict) -> None:
        """
        알림을 생성한다.
        
        Args:
            alert: 알림 정보 딕셔너리
        """
        pass
    
    @abstractmethod
    def update_subscription_last_seen(self, subscription_id: int, last_seen_post_id: str) -> None:
        """
        구독의 마지막 확인 게시글 ID를 업데이트한다.
        
        Args:
            subscription_id: 구독 ID
            last_seen_post_id: 마지막으로 확인한 게시글 ID
        """
        pass


class DefaultAlertService(AlertService):
    """기본 알림 서비스 구현체 (notification_client 래핑)"""
    
    def create_alert(self, alert: Dict) -> None:
        _create_alert(alert)
    
    def update_subscription_last_seen(self, subscription_id: int, last_seen_post_id: str) -> None:
        _update(subscription_id, last_seen_post_id)
