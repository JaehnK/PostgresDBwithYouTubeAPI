import os
from pathlib import Path
from typing import List, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv

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
    api_count = 1
    cookies_path: str = None
    
    def __post_init__(self):
        """설정 초기화 및 검증"""
        load_dotenv()   
        if not self.api_key:
            self.api_key = os.getenv('YOUTUBE_API_KEY' + str(self.api_count), '')
            
        if not self.cookies_path:
            self.cookies_path = os.getenv("YOUTUBE_COOKIES")
        
        # 출력 디렉토리 생성
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
    def _change_api(self):
        load_dotenv()
        self.api_count += 1
        self.api_key = os.getenv('YOUTUBE_API_KEY' + str(self.api_count), '')
        
    def validate(self) -> bool:
        """설정 유효성 검증"""
        return bool(self.api_key)
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        return getattr(self, key, default)
