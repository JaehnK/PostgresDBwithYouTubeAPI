"""
유동적 YouTube 서비스 아키텍처 구현
모듈화된 설계로 필요한 기능만 조합해서 사용 가능
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
import os
import json
import subprocess
import re
import time
import logging
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate


# ==================== 설정 관리 ====================
@dataclass
class YouTubeConfig:
    """YouTube 서비스 설정 중앙 관리"""
    api_key: str = ""
    output_dir: str = "./outputs"
    quota_limit_per_day: int = 10000
    rate_limit_delay: float = 0.1
    max_retries: int = 3
    retry_delay: int = 1
    max_results_per_request: int = 50
    default_subtitle_languages: List[str] = field(default_factory=lambda: ['ko', 'en'])
    auto_subtitles: bool = True
    
    def __post_init__(self):
        """설정 초기화 및 검증"""
        if not self.api_key:
            load_dotenv()
            self.api_key = os.getenv('YOUTUBE_API_KEY', '')
        
        # 출력 디렉토리 생성
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
    def validate(self) -> bool:
        """설정 유효성 검증"""
        return bool(self.api_key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        return getattr(self, key, default)


# ==================== 인터페이스 정의 ====================
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


class ISubtitleDownloader(ABC):
    """자막 다운로더 인터페이스"""
    
    @abstractmethod
    def download_subtitles(self, video_id: str, options: Dict[str, Any]) -> bool:
        pass
    
    @abstractmethod
    def list_available_subtitles(self, video_id: str) -> List[str]:
        pass


class ISubtitleProcessor(ABC):
    """자막 처리기 인터페이스"""
    
    @abstractmethod
    def convert_format(self, input_path: str, output_path: str, target_format: str) -> bool:
        pass
    
    @abstractmethod
    def extract_text(self, content: str) -> str:
        pass


# ==================== 유틸리티 클래스 ====================
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
            'video_url': f"https://www.youtube.com/watch?v={video_id}",
            'short_url': f"https://youtu.be/{video_id}",
            'embed_url': f"https://www.youtube.com/embed/{video_id}",
            'thumbnail_maxres': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        }


# ==================== 핵심 서비스 구현 ====================
class YouTubeAPIClient(IYouTubeAPIClient):
    """YouTube API 클라이언트 구현"""
    
    def __init__(self, config: YouTubeConfig):
        self.config = config
        self.youtube = build('youtube', 'v3', developerKey=config.api_key)
        self.quota_usage = 0
        self.last_call_time = 0
        self.logger = logging.getLogger(__name__)
    
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


class YTDLPDownloader(ISubtitleDownloader):
    """yt-dlp를 사용한 자막 다운로더"""
    
    def __init__(self, config: YouTubeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        if not self._check_ytdlp():
            raise RuntimeError("yt-dlp가 설치되지 않았습니다: pip install yt-dlp")
    
    def _check_ytdlp(self) -> bool:
        """yt-dlp 설치 확인"""
        try:
            subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def download_subtitles(self, video_id: str, options: Dict[str, Any]) -> bool:
        """자막 다운로드"""
        try:
            output_dir = options.get('output_dir', self.config.output_dir)
            languages = options.get('languages', self.config.default_subtitle_languages)
            auto_subs = options.get('auto_subs', self.config.auto_subtitles)
            
            # 출력 디렉토리 생성
            timestamp_dir = Path(output_dir) / "timestamp"
            timestamp_dir.mkdir(parents=True, exist_ok=True)
            
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            cmd = [
                'yt-dlp',
                '--skip-download',
                '--sub-format', 'srt',
                '--output', str(timestamp_dir / f'{video_id}.%(ext)s'),
                video_url
            ]
            
            if auto_subs:
                cmd.append('--write-auto-subs')
            cmd.append('--write-subs')
            
            if languages:
                cmd.extend(['--sub-langs', ','.join(languages)])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"자막 다운로드 성공: {video_id}")
                return True
            else:
                self.logger.error(f"자막 다운로드 실패: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"자막 다운로드 오류: {e}")
            return False
    
    def list_available_subtitles(self, video_id: str) -> List[str]:
        """사용 가능한 자막 목록 조회"""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = ['yt-dlp', '--list-subs', '--no-warnings', video_url]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 자막 언어 파싱 (간단한 구현)
                lines = result.stdout.split('\n')
                languages = []
                for line in lines:
                    if 'Available subtitles' in line or 'Available automatic captions' in line:
                        continue
                    if line.strip() and not line.startswith('Language'):
                        lang_match = re.match(r'^(\w+)', line.strip())
                        if lang_match:
                            languages.append(lang_match.group(1))
                return list(set(languages))
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"자막 목록 조회 오류: {e}")
            return []


class SubtitleProcessor(ISubtitleProcessor):
    """자막 처리기 구현"""
    
    def convert_format(self, input_path: str, output_path: str, target_format: str) -> bool:
        """자막 형식 변환"""
        try:
            if target_format.lower() == 'txt':
                return self._convert_to_text(input_path, output_path)
            else:
                raise ValueError(f"지원하지 않는 형식: {target_format}")
        except Exception as e:
            logging.error(f"형식 변환 오류: {e}")
            return False
    
    def _convert_to_text(self, input_path: str, output_path: str) -> bool:
        """SRT를 텍스트로 변환"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            text = self.extract_text(content)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            return True
        except Exception as e:
            logging.error(f"텍스트 변환 오류: {e}")
            return False
    
    def extract_text(self, content: str) -> str:
        """SRT 내용에서 텍스트만 추출"""
        if not content:
            return ""
        
        lines = content.split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # 번호나 타임스탬프가 아닌 실제 텍스트만 추출
            if line and not line.isdigit() and '-->' not in line:
                # HTML 태그 제거
                line = re.sub(r'<[^>]+>', '', line)
                text_lines.append(line)
        
        return ' '.join(text_lines)


# ==================== 고수준 서비스 ====================
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


class SubtitleManager:
    """자막 관리자"""
    
    def __init__(self, downloader: ISubtitleDownloader, processor: ISubtitleProcessor, utils: YouTubeUtils):
        self.downloader = downloader
        self.processor = processor
        self.utils = utils
    
    def collect_subtitles(self, video_id: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """자막 수집 및 처리"""
        try:
            # 1. 자막 다운로드
            download_success = self.downloader.download_subtitles(video_id, options)
            
            if not download_success:
                return {
                    'success': False,
                    'error': '자막 다운로드 실패'
                }
            
            # 2. 다운로드된 파일 처리
            output_dir = options.get('output_dir', './outputs')
            timestamp_dir = Path(output_dir) / "timestamp"
            text_dir = Path(output_dir) / "text_only"
            text_dir.mkdir(parents=True, exist_ok=True)
            
            processed_files = []
            
            # SRT 파일들을 텍스트로 변환
            for srt_file in timestamp_dir.glob(f"{video_id}*.srt"):
                text_file = text_dir / f"{video_id}.txt"
                if self.processor.convert_format(str(srt_file), str(text_file), 'txt'):
                    processed_files.append(str(text_file))
            
            return {
                'success': True,
                'timestamp_files': list(timestamp_dir.glob(f"{video_id}*.srt")),
                'text_files': processed_files
            }
            
        except Exception as e:
            logging.error(f"자막 수집 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# ==================== 팩토리 클래스 ====================
class YouTubeServiceFactory:
    """YouTube 서비스 팩토리"""
    
    def __init__(self, config: YouTubeConfig):
        self.config = config
        self.utils = YouTubeUtils()
    
    def create_api_client(self) -> IYouTubeAPIClient:
        """API 클라이언트 생성"""
        return YouTubeAPIClient(self.config)
    
    def create_subtitle_downloader(self) -> ISubtitleDownloader:
        """자막 다운로더 생성"""
        return YTDLPDownloader(self.config)
    
    def create_subtitle_processor(self) -> ISubtitleProcessor:
        """자막 처리기 생성"""
        return SubtitleProcessor()
    
    def create_metadata_extractor(self, api_client: IYouTubeAPIClient = None) -> VideoMetadataExtractor:
        """메타데이터 추출기 생성"""
        if api_client is None:
            api_client = self.create_api_client()
        return VideoMetadataExtractor(api_client, self.utils)
    
    def create_subtitle_manager(self, downloader: ISubtitleDownloader = None, 
                             processor: ISubtitleProcessor = None) -> SubtitleManager:
        """자막 관리자 생성"""
        if downloader is None:
            downloader = self.create_subtitle_downloader()
        if processor is None:
            processor = self.create_subtitle_processor()
        return SubtitleManager(downloader, processor, self.utils)


# ==================== 워크플로우 오케스트레이터 ====================
class YouTubeWorkflow:
    """YouTube 작업 워크플로우 관리"""
    
    def __init__(self, config: YouTubeConfig):
        self.config = config
        self.factory = YouTubeServiceFactory(config)
        self.logger = logging.getLogger(__name__)
    
    def process_single_video(self, video_url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """단일 비디오 전체 처리"""
        if options is None:
            options = {}
        
        try:
            # 비디오 ID 추출
            video_id = YouTubeUtils.extract_video_id(video_url)
            
            # 서비스 생성
            metadata_extractor = self.factory.create_metadata_extractor()
            subtitle_manager = self.factory.create_subtitle_manager()
            
            # 메타데이터 추출
            metadata = metadata_extractor.extract_full_metadata(video_id)
            
            # 자막 수집
            subtitle_options = {
                'output_dir': options.get('output_dir', self.config.output_dir),
                'languages': options.get('languages', self.config.default_subtitle_languages),
                'auto_subs': options.get('auto_subs', self.config.auto_subtitles)
            }
            
            subtitle_result = subtitle_manager.collect_subtitles(video_id, subtitle_options)
            
            return {
                'video_id': video_id,
                'metadata': metadata,
                'subtitles': subtitle_result,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"비디오 처리 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_metadata_only(self, video_url: str) -> Dict[str, Any]:
        """메타데이터만 추출"""
        try:
            video_id = YouTubeUtils.extract_video_id(video_url)
            metadata_extractor = self.factory.create_metadata_extractor()
            return metadata_extractor.extract_full_metadata(video_id)
        except Exception as e:
            self.logger.error(f"메타데이터 추출 오류: {e}")
            raise
    
    def download_subtitles_only(self, video_url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """자막만 다운로드"""
        if options is None:
            options = {}
        
        try:
            video_id = YouTubeUtils.extract_video_id(video_url)
            subtitle_manager = self.factory.create_subtitle_manager()
            
            subtitle_options = {
                'output_dir': options.get('output_dir', self.config.output_dir),
                'languages': options.get('languages', self.config.default_subtitle_languages),
                'auto_subs': options.get('auto_subs', self.config.auto_subtitles)
            }
            
            return subtitle_manager.collect_subtitles(video_id, subtitle_options)
            
        except Exception as e:
            self.logger.error(f"자막 다운로드 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# ==================== 사용 예제 ====================
def main():
    """사용 예제"""
    
    # 1. 설정 생성
    config = YouTubeConfig(
        output_dir="./youtube_outputs",
        default_subtitle_languages=['ko', 'en'],
        auto_subtitles=True
    )
    
    if not config.validate():
        print("❌ API 키가 설정되지 않았습니다.")
        return
    
    # 2. 워크플로우 생성
    workflow = YouTubeWorkflow(config)
    
    # 3. 다양한 사용 사례
    test_video = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print("🔍 사용 사례 1: 메타데이터만 추출")
    try:
        metadata = workflow.extract_metadata_only(test_video)
        print(f"제목: {metadata['title']}")
        print(f"채널: {metadata['channel_title']}")
        print(f"조회수: {metadata['view_count']:,}")
        print(f"재생시간: {metadata['duration_formatted']}")
    except Exception as e:
        print(f"오류: {e}")
    
    print("\n🔍 사용 사례 2: 자막만 다운로드")
    subtitle_result = workflow.download_subtitles_only(test_video, {
        'languages': ['ko', 'en'],
        'output_dir': './subtitles_only'
    })
    print(f"자막 다운로드 결과: {subtitle_result['success']}")
    
    print("\n🔍 사용 사례 3: 전체 처리")
    full_result = workflow.process_single_video(test_video, {
        'output_dir': './full_processing',
        'languages': ['ko']
    })
    
    if full_result['success']:
        print("✅ 전체 처리 완료")
        print(f"- 메타데이터: {len(full_result['metadata'])}개 필드")
        print(f"- 자막 파일: {len(full_result['subtitles'].get('text_files', []))}개")
    else:
        print(f"❌ 처리 실패: {full_result['error']}")
    
    print("\n🔍 사용 사례 4: 커스텀 조합")
    # 필요한 서비스만 직접 조합하여 사용
    factory = YouTubeServiceFactory(config)
    api_client = factory.create_api_client()
    
    try:
        video_id = YouTubeUtils.extract_video_id(test_video)
        video_info = api_client.get_video_info(video_id, ['snippet', 'statistics'])
        print(f"커스텀 조회 - 제목: {video_info['snippet']['title']}")
    except Exception as e:
        print(f"커스텀 조회 오류: {e}")


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    main()



"""
YouTube 서비스 다양한 사용 예제
필요한 기능만 조합해서 사용하는 방법들
"""

# from youtube_service import *  # 위에서 만든 모든 클래스들

# ==================== 사용 예제 1: 간단한 워크플로우 ====================
def example_1_simple_workflow():
    """가장 간단한 사용법 - 워크플로우 활용"""
    print("=" * 50)
    print("예제 1: 간단한 워크플로우")
    print("=" * 50)
    
    # 설정
    config = YouTubeConfig(
        output_dir="./example1_output",
        default_subtitle_languages=['ko']
    )
    
    # 워크플로우 생성
    workflow = YouTubeWorkflow(config)
    
    # 비디오 처리
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    result = workflow.process_single_video(video_url)
    
    if result['success']:
        metadata = result['metadata']
        print(f"✅ 처리 완료: {metadata['title']}")
        print(f"   채널: {metadata['channel_title']}")
        print(f"   조회수: {metadata['view_count']:,}")
        print(f"   자막 파일: {len(result['subtitles'].get('text_files', []))}개")
    else:
        print(f"❌ 처리 실패: {result['error']}")


# ==================== 사용 예제 2: 메타데이터만 필요한 경우 ====================
def example_2_metadata_only():
    """메타데이터만 필요한 경우"""
    print("\n" + "=" * 50)
    print("예제 2: 메타데이터만 추출")
    print("=" * 50)
    
    config = YouTubeConfig()
    factory = YouTubeServiceFactory(config)
    
    # 메타데이터 추출기만 생성
    metadata_extractor = factory.create_metadata_extractor()
    
    videos = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=9bZkp7q19f0"
    ]
    
    for video_url in videos:
        try:
            video_id = YouTubeUtils.extract_video_id(video_url)
            metadata = metadata_extractor.extract_full_metadata(video_id)
            
            print(f"\n📹 {metadata['title']}")
            print(f"   🎬 {metadata['channel_title']}")
            print(f"   👀 조회수: {metadata['view_count']:,}")
            print(f"   ⏱️ 재생시간: {metadata['duration_formatted']}")
            print(f"   👍 좋아요 비율: {metadata['like_ratio']:.3f}%")
            print(f"   💬 참여율: {metadata['engagement_rate']:.3f}%")
            
        except Exception as e:
            print(f"❌ {video_url} 처리 실패: {e}")


# ==================== 사용 예제 3: 자막만 필요한 경우 ====================
def example_3_subtitles_only():
    """자막만 필요한 경우"""
    print("\n" + "=" * 50)
    print("예제 3: 자막만 다운로드")
    print("=" * 50)
    
    config = YouTubeConfig(output_dir="./subtitle_downloads")
    factory = YouTubeServiceFactory(config)
    
    # 자막 관련 서비스만 생성
    subtitle_manager = factory.create_subtitle_manager()
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = YouTubeUtils.extract_video_id(video_url)
    
    # 다양한 언어로 자막 다운로드
    languages_to_try = [
        ['ko'],           # 한국어만
        ['en'],           # 영어만
        ['ko', 'en'],     # 한국어 + 영어
        ['ja', 'zh'],     # 일본어 + 중국어
    ]
    
    for languages in languages_to_try:
        print(f"\n🔍 언어 시도: {languages}")
        
        options = {
            'output_dir': f'./subtitles_{"-".join(languages)}',
            'languages': languages,
            'auto_subs': True
        }
        
        result = subtitle_manager.collect_subtitles(video_id, options)
        
        if result['success']:
            print(f"   ✅ 성공: {len(result['text_files'])}개 파일")
            for file_path in result['text_files']:
                print(f"      📄 {file_path}")
        else:
            print(f"   ❌ 실패: {result['error']}")


# ==================== 사용 예제 4: 커스텀 처리 파이프라인 ====================
def example_4_custom_pipeline():
    """커스텀 처리 파이프라인 구성"""
    print("\n" + "=" * 50)
    print("예제 4: 커스텀 처리 파이프라인")
    print("=" * 50)
    
    config = YouTubeConfig()
    factory = YouTubeServiceFactory(config)
    
    # 필요한 서비스들을 개별적으로 생성
    api_client = factory.create_api_client()
    subtitle_downloader = factory.create_subtitle_downloader()
    subtitle_processor = factory.create_subtitle_processor()
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = YouTubeUtils.extract_video_id(video_url)
    
    try:
        # 1단계: 기본 비디오 정보만 가져오기
        print("1️⃣ 기본 정보 조회...")
        video_info = api_client.get_video_info(video_id, ['snippet'])
        title = video_info['snippet']['title']
        print(f"   제목: {title}")
        
        # 2단계: 자막이 있는지 확인
        print("2️⃣ 자막 가용성 확인...")
        available_subs = subtitle_downloader.list_available_subtitles(video_id)
        print(f"   사용 가능한 언어: {available_subs}")
        
        if 'ko' in available_subs or 'en' in available_subs:
            # 3단계: 자막 다운로드
            print("3️⃣ 자막 다운로드...")
            download_options = {
                'output_dir': './custom_pipeline',
                'languages': ['ko', 'en'],
                'auto_subs': True
            }
            
            success = subtitle_downloader.download_subtitles(video_id, download_options)
            
            if success:
                # 4단계: 자막 텍스트 추출
                print("4️⃣ 텍스트 추출...")
                subtitle_files = list(Path('./custom_pipeline/timestamp').glob(f'{video_id}*.srt'))
                
                for srt_file in subtitle_files:
                    with open(srt_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    text = subtitle_processor.extract_text(content)
                    print(f"   📄 {srt_file.name}: {len(text)} 문자")
                    print(f"      미리보기: {text[:100]}...")
            else:
                print("   ❌ 자막 다운로드 실패")
        else:
            print("   ⚠️ 한국어/영어 자막 없음")
            
    except Exception as e:
        print(f"❌ 파이프라인 오류: {e}")


# ==================== 사용 예제 5: 배치 처리 ====================
def example_5_batch_processing():
    """여러 비디오 배치 처리"""
    print("\n" + "=" * 50)
    print("예제 5: 배치 처리")
    print("=" * 50)
    
    config = YouTubeConfig(
        output_dir="./batch_processing",
        rate_limit_delay=0.5  # 배치 처리시 더 긴 지연
    )
    
    workflow = YouTubeWorkflow(config)
    
    # 처리할 비디오 목록
    video_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=9bZkp7q19f0",
        # 더 많은 URL 추가 가능
    ]
    
    results = []
    
    for i, video_url in enumerate(video_urls, 1):
        print(f"\n🔄 [{i}/{len(video_urls)}] 처리 중: {video_url}")
        
        try:
            # 메타데이터만 추출 (빠른 처리)
            metadata = workflow.extract_metadata_only(video_url)
            
            result = {
                'url': video_url,
                'video_id': metadata['video_id'],
                'title': metadata['title'],
                'channel': metadata['channel_title'],
                'views': metadata['view_count'],
                'duration': metadata['duration_formatted'],
                'success': True
            }
            
            print(f"   ✅ 완료: {result['title']} ({result['views']:,} 조회수)")
            
        except Exception as e:
            result = {
                'url': video_url,
                'error': str(e),
                'success': False
            }
            print(f"   ❌ 실패: {e}")
        
        results.append(result)
        
        # API 호출 제한을 위한 짧은 대기
        time.sleep(0.5)
    
    # 결과 요약
    print(f"\n📊 배치 처리 완료")
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"   ✅ 성공: {len(successful)}개")
    print(f"   ❌ 실패: {len(failed)}개")
    
    if successful:
        total_views = sum(r['views'] for r in successful)
        print(f"   👀 총 조회수: {total_views:,}")
    
    return results


# ==================== 사용 예제 6: 채널 분석 ====================
def example_6_channel_analysis():
    """채널 전체 분석"""
    print("\n" + "=" * 50)
    print("예제 6: 채널 분석")
    print("=" * 50)
    
    config = YouTubeConfig()
    factory = YouTubeServiceFactory(config)
    
    api_client = factory.create_api_client()
    metadata_extractor = factory.create_metadata_extractor(api_client)
    
    # 채널 핸들로 분석
    channel_handle = "@YouTube"  # YouTube 공식 채널
    
    try:
        # 1. 채널 기본 정보
        print("1️⃣ 채널 정보 조회...")
        channel_info = api_client.get_channel_info(channel_handle)
        
        print(f"   📺 채널명: {channel_info['snippet']['title']}")
        print(f"   👥 구독자: {channel_info['statistics']['subscriberCount']:,}")
        print(f"   🎬 총 비디오: {channel_info['statistics']['videoCount']:,}")
        print(f"   👀 총 조회수: {channel_info['statistics']['viewCount']:,}")
        
        # 2. 최근 비디오들의 메타데이터 분석 (실제로는 playlist API 사용 필요)
        print("\n2️⃣ 인기 비디오 분석...")
        
        # 예시: 채널의 인기 비디오 몇 개 (실제로는 search API나 playlist API 사용)
        popular_videos = [
            "9bZkp7q19f0",  # 예시 비디오 ID
            # 실제로는 채널의 업로드 플레이리스트에서 가져와야 함
        ]
        
        for video_id in popular_videos:
            try:
                metadata = metadata_extractor.extract_full_metadata(video_id)
                print(f"   🎥 {metadata['title']}")
                print(f"      👀 {metadata['view_count']:,} 조회수")
                print(f"      👍 {metadata['like_ratio']:.2f}% 좋아요 비율")
                print(f"      💬 {metadata['engagement_rate']:.2f}% 참여율")
                
            except Exception as e:
                print(f"   ❌ 비디오 {video_id} 분석 실패: {e}")
        
    except Exception as e:
        print(f"❌ 채널 분석 실패: {e}")


# ==================== 사용 예제 7: 설정별 다른 동작 ====================
def example_7_different_configs():
    """다양한 설정으로 다른 동작 구현"""
    print("\n" + "=" * 50)
    print("예제 7: 설정별 다른 동작")
    print("=" * 50)
    
    # 설정 1: 빠른 처리 (메타데이터만)
    fast_config = YouTubeConfig(
        output_dir="./fast_processing",
        rate_limit_delay=0.1,
        default_subtitle_languages=[]  # 자막 다운로드 안 함
    )
    
    # 설정 2: 완전한 처리 (모든 자막)
    complete_config = YouTubeConfig(
        output_dir="./complete_processing",
        rate_limit_delay=0.5,
        default_subtitle_languages=['ko', 'en', 'ja', 'zh'],
        auto_subtitles=True
    )
    
    # 설정 3: 한국어 중심 처리
    korean_config = YouTubeConfig(
        output_dir="./korean_processing",
        default_subtitle_languages=['ko'],
        auto_subtitles=True
    )
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    configs = [
        ("빠른 처리", fast_config),
        ("완전한 처리", complete_config),
        ("한국어 중심", korean_config)
    ]
    
    for name, config in configs:
        print(f"\n🔧 {name} 설정으로 처리...")
        
        try:
            workflow = YouTubeWorkflow(config)
            
            if not config.default_subtitle_languages:
                # 메타데이터만 추출
                result = workflow.extract_metadata_only(video_url)
                print(f"   ✅ 메타데이터만 추출: {result['title']}")
            else:
                # 전체 처리
                result = workflow.process_single_video(video_url)
                if result['success']:
                    subtitle_count = len(result['subtitles'].get('text_files', []))
                    print(f"   ✅ 전체 처리 완료: {subtitle_count}개 자막 파일")
                else:
                    print(f"   ❌ 처리 실패: {result['error']}")
                    
        except Exception as e:
            print(f"   ❌ 설정 '{name}' 오류: {e}")


# ==================== 메인 실행 ====================
def main():
    """모든 예제 실행"""
    print("🚀 YouTube 서비스 사용 예제 실행")
    
    # 로깅 설정
    logging.basicConfig(level=logging.WARNING)  # 예제에서는 경고만 표시
    
    # 예제들 실행
    try:
        example_1_simple_workflow()
        example_2_metadata_only()
        example_3_subtitles_only()
        example_4_custom_pipeline()
        
        # 시간이 많이 걸릴 수 있는 예제들 (선택적 실행)
        run_batch_examples = input("\n⏰ 시간이 오래 걸리는 배치/채널 예제도 실행하시겠습니까? (y/N): ").lower() == 'y'
        
        if run_batch_examples:
            example_5_batch_processing()
            example_6_channel_analysis()
        
        example_7_different_configs()
        
        print("\n🎉 모든 예제 실행 완료!")
        
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n❌ 예제 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()