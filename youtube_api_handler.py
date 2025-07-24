import os
import time
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging


class YouTubeAPIHandler:
    def __init__(self, max_results: int = 50, quota_limit_per_day: int = 10000):
        """
        YouTube API 핸들러 초기화
        
        Args:
            max_results (int): 한 번의 요청에서 가져올 최대 결과 수 (기본값: 50)
            quota_limit_per_day (int): 일일 할당량 제한 (기본값: 10,000)
        """
        
        load_dotenv()
        
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        print(f"Your API Key is {self.api_key}")
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        
        # 기본 설정값들
        self.max_results = max_results
        self.quota_limit_per_day = quota_limit_per_day
        self.current_quota_usage = 0
        
        # API 호출 간격 (Rate Limiting)
        self.api_call_delay = 0.1  # 100ms
        self.last_api_call_time = 0
        
        # 로깅 설정
        self.logger = logging.getLogger(__name__)
        
        # 에러 재시도 설정
        self.max_retries = 3
        self.retry_delay = 1  # 초
        
        # API 응답 필드 설정
        self.default_video_parts = ['snippet', 'statistics', 'contentDetails']
        self.default_channel_parts = ['snippet', 'statistics', 'contentDetails']
        self.default_playlist_parts = ['snippet', 'contentDetails']
        
        # 페이지네이션 설정
        self.max_pages = 10  # 최대 페이지 수 제한
        
        self.logger.info("YouTube API Handler 초기화 완료")
    
    def _wait_for_rate_limit(self):
        """API 호출 간격 조절"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call_time
        
        if time_since_last_call < self.api_call_delay:
            time.sleep(self.api_call_delay - time_since_last_call)
        
        self.last_api_call_time = time.time()
    
    def _check_quota_limit(self, estimated_cost: int = 1):
        """할당량 제한 확인"""
        if self.current_quota_usage + estimated_cost > self.quota_limit_per_day:
            raise Exception(f"일일 할당량 초과 위험: {self.current_quota_usage}/{self.quota_limit_per_day}")
        
    def get_channel_info(self, channel_id: str, parts: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        채널 정보 조회
        
        Args:
            channel_id (str): YouTube 채널 ID
            parts (Optional[List[str]]): 가져올 정보 부분들
            
        Returns:
            Dict[str, Any]: 채널 정보
        """
        if parts is None:
            parts = self.default_channel_parts
        
        try:
            # 할당량 체크
            self._check_quota_limit(1)
            
            # Rate limiting
            self._wait_for_rate_limit()
            
            # API 호출
            request = self.youtube.channels().list(
                part=','.join(parts),
                # id=channel_id
                forHandle = channel_id
            )
            
            response = request.execute()
            self.current_quota_usage += 1
            
            if response['items']:
                channel_data = response['items'][0]
                
                # 채널 정보 정리
                channel_info = {
                    'channel_id': channel_data['id'],
                    'title': channel_data['snippet']['title'],
                    'description': channel_data['snippet']['description'],
                    'published_at': channel_data['snippet']['publishedAt'],
                    'thumbnail_url': channel_data['snippet']['thumbnails']['default']['url'],
                    'country': channel_data['snippet'].get('country', ''),
                    'view_count': int(channel_data['statistics']['viewCount']),
                    'subscriber_count': int(channel_data['statistics']['subscriberCount']),
                    'video_count': int(channel_data['statistics']['videoCount']),
                    'raw_data': channel_data  # 원본 데이터도 포함
                }
                
                self.logger.info(f"채널 정보 조회 성공: {channel_info['title']}")
                return channel_info
            else:
                raise ValueError(f"채널을 찾을 수 없습니다: {channel_id}")
                
        except HttpError as e:
            self.logger.error(f"YouTube API 오류: {e}")
            if e.resp.status == 403:
                raise Exception("API 할당량 초과 또는 권한 오류")
            elif e.resp.status == 404:
                raise ValueError(f"채널을 찾을 수 없습니다: {channel_id}")
            else:
                raise Exception(f"API 호출 실패: {e}")
            self.get_channel_info()
        except Exception as e:
            self.logger.error(f"채널 정보 조회 중 오류: {e}")
            raise
    
    def get_all_videos(self, handle: str, parts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        YouTube 핸들(@계정명)을 기반으로 해당 채널의 모든 영상을 반환
        
        Args:
            handle (str): @계정명 형식의 YouTube 핸들
            parts (Optional[List[str]]): 채널 조회 시 필요한 정보 파트
        
        Returns:
            List[Dict[str, Any]]: 채널의 모든 영상 정보 목록
        """
        if parts is None:
            parts = self.default_channel_parts
        
        try:
            # 1. 핸들로 채널 정보 조회
            channel_info = self.get_channel_info(handle, parts=parts)
            channel_id = channel_info['channel_id']
            uploads_playlist_id = channel_info['raw_data']['contentDetails']['relatedPlaylists']['uploads']
            
            # 2. 업로드된 모든 영상 수집
            videos = []
            next_page_token = None
            
            while True:
                self._check_quota_limit(1)
                self._wait_for_rate_limit()
                
                request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                
                response = request.execute()
                self.current_quota_usage += 1
                
                for item in response['items']:
                    videos.append({
                        'video_id': item['contentDetails']['videoId'],
                        'published_at': item['contentDetails']['videoPublishedAt'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'thumbnails': item['snippet']['thumbnails'],
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            self.logger.info(f"{handle}의 영상 {len(videos)}개 조회 성공")
            return videos
        
        except HttpError as e:
            self.logger.error(f"YouTube API 오류: {e}")
            raise Exception("API 오류 발생")
        except Exception as e:
            self.logger.error(f"영상 조회 중 오류: {e}")
            raise

    
    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        비디오 정보 조회
        
        Args:
            video_id (str): YouTube 비디오 ID
            
        Returns:
            Dict[str, Any]: 비디오 정보
        """
        # 여기에 실제 API 호출 로직 구현
        pass
    
    def search_videos(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        비디오 검색
        
        Args:
            query (str): 검색 쿼리
            max_results (Optional[int]): 최대 결과 수
            
        Returns:
            List[Dict[str, Any]]: 검색된 비디오 목록
        """
        # 여기에 실제 검색 로직 구현
        pass