from typing import Dict, Any
import logging
from pprint import pprint

from googleapiclient.errors import HttpError
from .utils.YoutubeUtils import YouTubeUtils

import json
from .dao.YouTubeDao import YouTubeDBSetup

from .YouTubeConfig import YouTubeConfig
from .YouTubeServiceFactory import YouTubeServiceFactory

from .services.YouTubeAPIClient import YouTubeAPIClient


class YouTubeWorkflow:
    """YouTube 작업 워크플로우 관리"""
    
    def __init__(self, config: YouTubeConfig):
        self.config = config
        self.factory = YouTubeServiceFactory(config)
        self.logger = logging.getLogger(__name__)
    
    def process_single_video(self, video_url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """단일 비디오 전체 처리 (댓글 기능 추가)"""
        if options is None:
            options = {}
        
        try:
            # 비디오 ID 추출
            video_id = YouTubeUtils.extract_video_id(video_url)
            
            # 서비스 생성
            metadata_extractor = self.factory.create_metadata_extractor()
            subtitle_manager = self.factory.create_subtitle_manager()
            db_connector = self.factory.create_db_connector()
            
            # 메타데이터 추출 
            metadata = metadata_extractor.extract_full_metadata(video_id)
            
            # 자막 수집
            subtitle_options = {
                'output_dir': options.get('output_dir', self.config.output_dir),
                'languages': options.get('languages', self.config.default_subtitle_languages),
                'auto_subs': options.get('auto_subs', self.config.auto_subtitles)
            }
            subtitle_result = subtitle_manager.collect_subtitles(video_id, subtitle_options)
            
            #pprint(subtitle_result)
            metadata['script_timestamp'] = subtitle_result['timestamp_files'][0]
            metadata['script'] = subtitle_result['text_files']
            db_connector.save_video_data(metadata)
            results = {
                'video_id': video_id,
                'metadata': metadata,
                #'subtitles': subtitle_result,
                'success': True
            }
            
            # 댓글 기능 (옵션으로만 실행)
            if options.get('include_comments', True):
                comment_collector = self.factory.create_comment_collector()
                all_comments = comment_collector.collect_complete_comments(video_id)
                
                # 분석 및 결과 구성
                results['comments'] = {
                    'total_comments': len(all_comments),
                    'structure_analysis': comment_collector.analyze_comment_structure(all_comments),
                    'quota_used': comment_collector.quota_usage
                }
                
                if options.get('include_raw_comments', True):
                    results['comments']['raw_comments'] = all_comments
                for coms in results['comments']['raw_comments']:
                    db_connector.save_comment_data(coms)
                return results
            
        except HttpError as e:
            
        # 에러 상세 정보 파싱
            error_details = json.loads(e.content.decode('utf-8'))
            error_reason = error_details.get('error', {}).get('errors', [{}])[0].get('reason', '')
            if e.resp.status == 403:
                if error_reason == 'quotaExceeded':
                    print("API 할당량이 초과되었습니다. 재갱신 하겠습니다.")
                    self.config._change_api()
                    self.factory = YouTubeServiceFactory(self.config)
                    return self.process_single_video(video_url, options)
                    # quota exceeded 전용 처리 로직
                elif error_reason == 'forbidden':
                    print("접근이 금지되었습니다.")
                else:
                    print(f"403 에러 (다른 원인): {error_reason}")
            else:
                print(f"다른 HTTP 에러: {e.resp.status}, {error_reason}")
                
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
            
    def process_channel_information(self, channel_handler: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        
        channel_extractor = self.factory.create_channel_metadata_extractor()
        channel_data = channel_extractor.get_channel_data(channel_handler)
        database = self.factory.create_db_connector()
        database.save_channel_data(channel_data)

        results = {
                'channel_handler': channel_handler,
                'metadata': channel_data,
                'success': True
            }
        
        return results