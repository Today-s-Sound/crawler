from abc import ABC, abstractmethod
from services.summarizer import summarize as _summarize

class SummarizerService(ABC):
    """요약 서비스 인터페이스"""
    
    @abstractmethod
    def summarize(self, text: str, max_chars: int = 300) -> str:
        """
        텍스트를 요약한다.
        
        Args:
            text: 요약할 텍스트
            max_chars: 최대 문자 수 (기본값: 300)
            
        Returns:
            요약된 텍스트
        """
        pass


class DefaultSummarizerService(SummarizerService):
    """기본 요약 서비스 구현체 (기존 summarizer 래핑)"""
    
    def summarize(self, text: str, max_chars: int = 300) -> str:
        return _summarize(text, max_chars)
