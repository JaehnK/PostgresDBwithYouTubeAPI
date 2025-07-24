from abc import ABC, abstractmethod
from typing import Dict, List, Any

class ICommentCollector(ABC):
    """댓글 수집기 인터페이스"""
    
    @abstractmethod
    def get_video_comments(self, video_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """비디오 댓글 수집"""
        pass
    
    @abstractmethod
    def collect_complete_comments(self, video_id: str) -> List[Dict[str, Any]]:
        """모든 댓글과 대댓글을 완전히 수집"""
        pass
    
    @abstractmethod
    def analyze_comment_structure(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """댓글 구조 분석"""
        pass