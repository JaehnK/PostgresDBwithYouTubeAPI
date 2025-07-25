from typing import Dict, Any
from pathlib import Path
import logging

from ..interfaces.ISubtitleDownloader import ISubtitleDownloader
from ..interfaces.ISubtitleProcessor import ISubtitleProcessor
from ..utils.YoutubeUtils import YouTubeUtils

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
            print("Script Download: ", download_success)
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
                'timestamp_files': [str(file) for file in timestamp_dir.glob(f"{video_id}*.srt")],
                'text_files': processed_files[0]
            }
            
        except Exception as e:
            logging.error(f"자막 수집 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }
