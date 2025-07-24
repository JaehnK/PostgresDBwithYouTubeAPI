from typing import Dict, List, Any 
from abc import ABC, abstractmethod

class IYouTubeAPIClient(ABC):
    """YouTube API 클라이언트 인터페이스"""
    
    @abstractmethod
    def get_video_info(self, video_id: str, parts: List[str] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_channel_info(self, channel_id: str, parts: List[str] = None) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def search_videos(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        pass