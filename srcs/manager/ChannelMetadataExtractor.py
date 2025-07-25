from typing import Dict, Any, Optional
from datetime import datetime

from ..interfaces.IYouTubeAPIClient import IYouTubeAPIClient


class ChannelMetadataExtractor:
    """YouTube 채널 정보를 조회하고 DB 스키마에 맞게 변환하는 매니저 클래스"""
    
    def __init__(self, api_client: IYouTubeAPIClient):
        self.api_client = api_client
    
    def get_channel_data(self, channel_handler: str) -> Dict[str, Any]:
        """
        채널 정보를 조회하고 DB에 삽입할 수 있는 형태로 변환
        
        Args:
            channel_handler: 채널 ID 또는 핸들 (@채널명)
            
        Returns:
            DB에 삽입할 수 있는 형태의 dict
        """
        # API 호출
        raw_data = self.api_client.get_channel_info(channel_handler)
        
        # 변환하여 반환
        return self._transform(raw_data)
    
    def _transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        YouTube API의 raw 채널 데이터를 DB 테이블 구조에 맞게 변환
        
        Args:
            raw_data: YouTubeAPIClient.get_channel_info()의 응답 데이터
            
        Returns:
            DB에 삽입할 수 있는 형태의 dict
        """
        snippet = raw_data.get('snippet', {})
        statistics = raw_data.get('statistics', {})
        
        return {
            'channel_id': raw_data.get('id'),
            'customUrl': snippet.get('customUrl'),
            'title': snippet.get('title'),
            'country': snippet.get('country'),
            'description': snippet.get('description'),
            'published_at': snippet.get('publishedAt'),
            'etag': raw_data.get('etag'),
            'hiddenSubscriberCount': statistics.get('hiddenSubscriberCount', False),
            'subscriberCount': self._safe_int_convert(statistics.get('subscriberCount')),
            'videoCount': self._safe_int_convert(statistics.get('videoCount')),
            'viewCount': self._safe_int_convert(statistics.get('viewCount')),
            'thumbnail_url': self._extract_thumbnail_url(snippet.get('thumbnails', {})),
            'collection_time': datetime.now().isoformat() + 'Z'
        }
    
    def _safe_int_convert(self, value: Any) -> Optional[int]:
        """문자열이나 None을 안전하게 정수로 변환"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _extract_thumbnail_url(self, thumbnails: Dict[str, Any]) -> Optional[str]:
        """썸네일 URL 추출 (high > medium > default 순서로 우선순위)"""
        if not thumbnails:
            return None
            
        # 우선순위: high > medium > default
        for quality in ['high', 'medium', 'default']:
            if quality in thumbnails and 'url' in thumbnails[quality]:
                return thumbnails[quality]['url']
        
        return None