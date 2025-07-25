import re
from typing import Dict 
import isodate

class YouTubeUtils:
    """YouTube 관련 유틸리티 함수들"""
    
    @staticmethod
    def extract_video_id(url_or_id: str) -> str:
        """YouTube URL에서 비디오 ID 추출"""
        if len(url_or_id) == 11 and not '/' in url_or_id:
            return url_or_id
        
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        raise ValueError(f"올바른 YouTube URL 또는 비디오 ID가 아닙니다: {url_or_id}")
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """초를 시:분:초 형식으로 변환"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    @staticmethod
    def parse_iso_duration(iso_duration: str) -> int:
        """ISO 8601 duration을 초로 변환"""
        try:
            return int(isodate.parse_duration(iso_duration).total_seconds())
        except:
            return 0
    
    @staticmethod
    def generate_urls(video_id: str) -> Dict[str, str]:
        """비디오 ID로부터 관련 URL 생성"""
        return {
            #'video_url': f"https://www.youtube.com/watch?v={video_id}",
            #'short_url': f"https://youtu.be/{video_id}",
            #'embed_url': f"https://www.youtube.com/embed/{video_id}",
            'thumbnail_maxres': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        }