from .interfaces.ISubtitleDownloader import ISubtitleDownloader
from .interfaces.ISubtitleProcessor import ISubtitleProcessor
from .interfaces.IYouTubeAPIClient import IYouTubeAPIClient

from .manager.VideoMetaDataExtractor import VideoMetadataExtractor
from .manager.SubtitleManager import SubtitleManager

from .services.SubtitleProcessor import SubtitleProcessor
from .services.YouTubeAPIClient import YouTubeAPIClient
from .services.YTDLPDownLoader import YTDLPDownloader
from .services.YouTubeCommentCollector import YouTubeCommentCollector

from .utils.YoutubeUtils import YouTubeUtils
from .YouTubeConfig import YouTubeConfig

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
    
    def create_comment_collector(self) -> YouTubeCommentCollector:
        """댓글 수집기 생성"""
        return YouTubeCommentCollector(self.config)