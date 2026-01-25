from typing import Dict, Optional


class CacheManager:
    """
    캐시 관리 책임을 분리한 클래스
    - 본문(content) 캐시와 요약(summary) 캐시를 관리
    """
    
    def __init__(self):
        self._content_cache: Dict[str, str] = {}
        self._summary_cache: Dict[str, str] = {}
    
    def get_content(self, key: str) -> Optional[str]:
        """
        본문 캐시에서 값을 가져온다.
        
        Args:
            key: 캐시 키 (게시글 ID 또는 URL)
            
        Returns:
            캐시된 본문 텍스트, 없으면 None
        """
        return self._content_cache.get(key)
    
    def set_content(self, key: str, value: str) -> None:
        """
        본문을 캐시에 저장한다.
        
        Args:
            key: 캐시 키
            value: 본문 텍스트
        """
        self._content_cache[key] = value
    
    def get_summary(self, key: str) -> Optional[str]:
        """
        요약 캐시에서 값을 가져온다.
        
        Args:
            key: 캐시 키 (게시글 ID 또는 URL)
            
        Returns:
            캐시된 요약 텍스트, 없으면 None
        """
        return self._summary_cache.get(key)
    
    def set_summary(self, key: str, value: str) -> None:
        """
        요약을 캐시에 저장한다.
        
        Args:
            key: 캐시 키
            value: 요약 텍스트
        """
        self._summary_cache[key] = value
    
    def clear(self) -> None:
        """모든 캐시를 비운다."""
        self._content_cache.clear()
        self._summary_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        캐시 통계를 반환한다.
        
        Returns:
            content_count, summary_count를 포함한 딕셔너리
        """
        return {
            "content_count": len(self._content_cache),
            "summary_count": len(self._summary_cache),
        }
