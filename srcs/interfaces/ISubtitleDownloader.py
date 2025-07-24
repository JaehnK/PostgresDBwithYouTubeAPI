from abc import ABC, abstractmethod
from typing import Dict, List, Any

class ISubtitleDownloader(ABC):
    """자막 다운로더 인터페이스"""
    
    @abstractmethod
    def download_subtitles(self, video_id: str, options: Dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    def list_available_subtitles(self, video_id: str) -> List[str]:
        pass