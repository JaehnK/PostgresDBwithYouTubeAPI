import time
import logging
import os
from typing import Dict, List, Any
import json

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..interfaces import IYouTubeAPIClient
from ..YouTubeConfig import YouTubeConfig


class YouTubeAPIClient(IYouTubeAPIClient):
    """YouTube API 클라이언트 구현"""
    
    def __init__(self, config: YouTubeConfig):
        self.api_count = 1
        self.config = config
        self.youtube = build('youtube', 'v3', developerKey=config.api_key)
        self.quota_usage = 0
        self.last_call_time = 0
        self.logger = logging.getLogger(__name__)
        
    def _reload_api(self):
        self.api_count += 1
        self.config._change_api()
        self.youtube = build('youtube', 'v3', developerKey=self.config.api_key)
        
    def _rate_limit(self):
        """API 호출 제한"""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - time_since_last)
        
        self.last_call_time = time.time()
    
    def _check_quota(self, cost: int = 1) -> bool:
        """할당량 확인"""
        if self.quota_usage + cost > self.config.quota_limit_per_day:
            raise Exception(f"일일 할당량 초과 위험: {self.quota_usage}/{self.config.quota_limit_per_day}")
        return True
    
    def get_video_info(self, video_id: str, parts: List[str] = None) -> Dict[str, Any]:
        """비디오 정보 조회"""
        if parts is None:
            parts = ['snippet', 'statistics', 'contentDetails']
        
        self._check_quota(1)
        self._rate_limit()
        
        try:
            request = self.youtube.videos().list(
                part=','.join(parts),
                id=video_id
            )
            response = request.execute()
            self.quota_usage += 1
            
            if response['items']:
                return response['items'][0]
            else:
                raise ValueError(f"비디오를 찾을 수 없습니다: {video_id}")
        except HttpError as e:
            self.logger.error(f"YouTube API 오류: {e}")
            raise
    
    def get_channel_info(self, channel_id: str, parts: List[str] = None) -> Dict[str, Any]:
        """채널 정보 조회 (핸들 지원)"""
        if parts is None:
            parts = ['snippet', 'statistics', 'contentDetails']
        
        self._check_quota(1)
        self._rate_limit()
        
        try:
            # 핸들인지 채널 ID인지 판단
            if channel_id.startswith('@'):
                request = self.youtube.channels().list(
                    part=','.join(parts),
                    forHandle=channel_id
                )
            else:
                request = self.youtube.channels().list(
                    part=','.join(parts),
                    id=channel_id
                )
            
            response = request.execute()
            self.quota_usage += 1
            
            if response['items']:
                return response['items'][0]
            else:
                raise ValueError(f"채널을 찾을 수 없습니다: {channel_id}")
                
        except HttpError as e:
            self.logger.error(f"YouTube API 오류: {e}")
            raise
    
    def search_videos(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """비디오 검색"""
        self._check_quota(100)  # 검색은 100 할당량 소모
        self._rate_limit()
        
        try:
            request = self.youtube.search().list(
                part='snippet',
                q=query,
                type='video',
                maxResults=min(max_results, self.config.max_results_per_request)
            )
            response = request.execute()
            self.quota_usage += 100
            
            return response.get('items', [])
            
        except HttpError as e:
            self.logger.error(f"YouTube API 오류: {e}")
            raise
