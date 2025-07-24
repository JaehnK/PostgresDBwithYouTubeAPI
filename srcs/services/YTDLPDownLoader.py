from typing import Dict, List, Any
from pathlib import Path
import subprocess
import logging
import re

from ..YouTubeConfig import YouTubeConfig
from ..interfaces import ISubtitleDownloader

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