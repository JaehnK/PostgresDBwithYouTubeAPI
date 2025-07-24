import logging
from typing import Dict, Any

from ..utils.YoutubeUtils import YouTubeUtils
from ..interfaces.IYouTubeAPIClient import IYouTubeAPIClient

class VideoMetadataExtractor:
    """비디오 메타데이터 추출기"""
    
    def __init__(self, api_client: IYouTubeAPIClient, utils: YouTubeUtils):
        self.api_client = api_client
        self.utils = utils
    
    def extract_full_metadata(self, video_id: str) -> Dict[str, Any]:
        """완전한 메타데이터 추출"""
        try:
            # API에서 기본 정보 가져오기
            video_data = self.api_client.get_video_info(video_id)
            
            # 메타데이터 구성
            metadata = {
                'video_id': video_id,
                'title': video_data['snippet']['title'],
                'channel_title': video_data['snippet']['channelTitle'],
                'channel_id': video_data['snippet']['channelId'],
                'published_at': video_data['snippet']['publishedAt'],
                'description': video_data['snippet']['description'],
                'tags': video_data['snippet'].get('tags', []),
                'category_id': video_data['snippet']['categoryId'],
                'view_count': int(video_data['statistics'].get('viewCount', 0)),
                'like_count': int(video_data['statistics'].get('likeCount', 0)),
                'comment_count': int(video_data['statistics'].get('commentCount', 0)),
                'duration_iso': video_data['contentDetails']['duration'],
                'definition': video_data['contentDetails']['definition'],
                'caption': video_data['contentDetails']['caption'],
            }
            
            # 추가 계산 필드
            metadata['duration_seconds'] = self.utils.parse_iso_duration(metadata['duration_iso'])
            metadata['duration_formatted'] = self.utils.format_duration(metadata['duration_seconds'])
            metadata.update(self.utils.generate_urls(video_id))
            metadata.update(self.calculate_analytics(metadata))
            
            return metadata
            
        except Exception as e:
            logging.error(f"메타데이터 추출 오류: {e}")
            raise
    
    def calculate_analytics(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """분석 지표 계산"""
        views = metadata.get('view_count', 0)
        likes = metadata.get('like_count', 0)
        comments = metadata.get('comment_count', 0)
        
        analytics = {}
        
        if views > 0:
            analytics['like_ratio'] = round((likes / views) * 100, 3)
            analytics['engagement_rate'] = round(((likes + comments) / views) * 100, 3)
        else:
            analytics['like_ratio'] = 0
            analytics['engagement_rate'] = 0
        
        return analytics
