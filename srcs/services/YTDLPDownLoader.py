from typing import Dict, List, Any
from pathlib import Path
import subprocess
import random
import logging
import time
import re

from ..YouTubeConfig import YouTubeConfig
from ..interfaces import ISubtitleDownloader

class YTDLPDownloader(ISubtitleDownloader):
    """yt-dlp를 사용한 자막 다운로더"""
    
    def __init__(self, config: YouTubeConfig):
        print("YT-DLP init ...")
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
        """자막 다운로드 - Rate limiting 및 재시도 로직 포함"""
        max_retries = 3
        base_delay = 2  # 기본 대기 시간 (초)
        
        try:
            output_dir = options.get('output_dir', self.config.output_dir)
            languages = options.get('languages', self.config.default_subtitle_languages)
            auto_subs = options.get('auto_subs', self.config.auto_subtitles)
            
            # 출력 디렉토리 생성
            timestamp_dir = Path(output_dir) / "timestamp"
            timestamp_dir.mkdir(parents=True, exist_ok=True)
            
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # 쿠키 파일 경로 확인
            cookies_path = options.get('cookies_path', self.config.cookies_path)
            
            # 기본 명령어 구성
            cmd = [
                'yt-dlp',
                '--skip-download',
                '--sub-format', 'srt',
                '--output', str(timestamp_dir / f'{video_id}.%(ext)s'),
                # Rate limiting 관련 옵션들
                '--sleep-interval', '1',        # 요청 간 1초 대기
                '--max-sleep-interval', '5',    # 최대 5초까지 랜덤 대기
                '--sleep-subtitles', '1',       # 자막 요청 간 1초 대기
            ]
            
            # 쿠키 파일이 있으면 추가
            if cookies_path and Path(cookies_path).exists():
                cmd.extend(['--cookies', str(cookies_path)])
                self.logger.info(f"쿠키 파일 사용: {cookies_path}")
            else:
                self.logger.warning("쿠키 파일이 없습니다. Rate limiting이 더 엄격할 수 있습니다.")
            
            cmd.append(video_url)
            
            if auto_subs:
                cmd.append('--write-auto-subs')
            cmd.append('--write-subs')
            
            if languages:
                cmd.extend(['--sub-langs', ','.join(languages)])
            
            # 재시도 로직
            for attempt in range(max_retries):
                try:
                    # 각 시도 전에 지연 (첫 번째 시도 제외)
                    if attempt > 0:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        self.logger.info(f"재시도 {attempt + 1}/{max_retries}, {delay:.1f}초 대기 중...")
                        time.sleep(delay)
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    
                    if result.returncode == 0:
                        self.logger.info(f"자막 다운로드 성공: {video_id}")
                        return True
                    elif "429" in result.stderr or "Too Many Requests" in result.stderr:
                        self.logger.warning(f"Rate limit 감지 (시도 {attempt + 1}/{max_retries}): {video_id}")
                        if attempt == max_retries - 1:
                            self.logger.error(f"최대 재시도 횟수 초과: {video_id}")
                            return False
                        continue
                    else:
                        self.logger.error(f"자막 다운로드 실패: {result.stderr}")
                        return False
                        
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"시간 초과 (시도 {attempt + 1}/{max_retries}): {video_id}")
                    if attempt == max_retries - 1:
                        return False
                    continue
                    
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