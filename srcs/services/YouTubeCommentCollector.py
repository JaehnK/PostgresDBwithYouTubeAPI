from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import os
import time
import logging
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..YouTubeConfig import YouTubeConfig
from ..interfaces import ICommentCollector


# ==================== 무제한 댓글 수집기 구현 ====================
class YouTubeCommentCollector(ICommentCollector):
    """YouTube API를 사용한 무제한 댓글 수집기 (모든 댓글과 대댓글 수집)"""
    
    def __init__(self, config):
        self.config = config
        self.youtube = build('youtube', 'v3', developerKey=config.api_key)
        self.quota_usage = 0
        self._last_call_time = 0
        self._logger = logging.getLogger(__name__)
    
    # ==================== PUBLIC 메서드 (인터페이스 구현) ====================
    
    def get_video_comments(self, video_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """비디오 댓글 수집 (제한된 수량)"""
        self._logger.info(f"댓글 수집 시작: {video_id} (최대 {max_results}개)")
        
        comments = []
        next_page_token = None
        collected = 0
        max_retries = self.config.max_retries
        
        while collected < max_results:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    self._check_quota(1)
                    self._rate_limit()
                    
                    per_page = min(100, max_results - collected)
                    
                    request = self.youtube.commentThreads().list(
                        part='snippet,replies',
                        videoId=video_id,
                        maxResults=per_page,
                        order='time',
                        pageToken=next_page_token if next_page_token else None
                    )
                    
                    response = request.execute()
                    self.quota_usage += 1
                    
                    for item in response.get('items', []):
                        if collected >= max_results:
                            break
                            
                        comment_data = self._extract_comment_data(item, video_id)
                        comments.append(comment_data)
                        collected += 1
                    
                    next_page_token = response.get('nextPageToken')
                    if not next_page_token:
                        break
                    break  # 성공시 재시도 루프 종료
                        
                except HttpError as e:
                    if self._handle_api_error(e, "댓글 수집"):
                        retry_count += 1
                        continue
                    else:
                        self._logger.error(f"API 요청 실패: {e}")
                        return comments
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        self._logger.error(f"댓글 수집 중 오류 (최대 재시도 초과): {e}")
                        return comments
                    
                    self._logger.warning(f"댓글 수집 재시도 {retry_count}/{max_retries}: {e}")
                    time.sleep(self.config.retry_delay * retry_count)
        
        self._logger.info(f"댓글 수집 완료: {len(comments)}개")
        return comments
    
    def collect_complete_comments(self, video_id: str) -> List[Dict[str, Any]]:
        """모든 댓글과 대댓글을 완전히 수집 (무제한)"""
        self._logger.info(f"🚀 비디오 ID: {video_id} - 무제한 댓글 수집 시작")
        
        all_comments = []
        next_page_token = None
        page_count = 0
        max_retries = self.config.max_retries
        total_threads_processed = 0
        
        while True:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    self._check_quota(1)
                    self._rate_limit()
                    
                    request = self.youtube.commentThreads().list(
                        part='snippet,replies',
                        videoId=video_id,
                        maxResults=100,  # 최대값 사용
                        order='time',
                        pageToken=next_page_token if next_page_token else None
                    )
                    
                    response = request.execute()
                    self.quota_usage += 1
                    page_count += 1
                    page_comments = 0
                    
                    for item in response.get('items', []):
                        total_threads_processed += 1
                        
                        # 1. 최상위 댓글 추가
                        top_comment = self._extract_comment_data(item, video_id)
                        all_comments.append(top_comment)
                        page_comments += 1
                        
                        # 2. API 응답에 포함된 답글들 처리
                        api_replies = []
                        if 'replies' in item:
                            for reply in item['replies']['comments']:
                                reply_data = self._extract_comment_data(reply, video_id, is_reply=True, parent_id=item['id'])
                                api_replies.append(reply_data)
                                all_comments.append(reply_data)
                                page_comments += 1
                        
                        # 3. 답글이 더 있는 경우 모든 답글 수집 (무제한)
                        total_reply_count = item['snippet']['totalReplyCount']
                        if total_reply_count > len(api_replies):
                            self._logger.info(f"📝 댓글 {item['id']}: {total_reply_count}개 답글 중 {len(api_replies)}개만 로드됨")
                            self._logger.info(f"   🔄 나머지 {total_reply_count - len(api_replies)}개 답글 수집 중...")
                            
                            # 모든 답글 별도 수집 (무제한)
                            complete_replies = self._get_all_replies(item['id'], video_id)
                            
                            # API 응답에 이미 포함된 답글 제외
                            api_reply_ids = {reply['comment_id'] for reply in api_replies}
                            new_replies = [reply for reply in complete_replies if reply['comment_id'] not in api_reply_ids]
                            
                            all_comments.extend(new_replies)
                            page_comments += len(new_replies)
                            
                            if len(new_replies) > 0:
                                self._logger.info(f"   ✅ 추가 답글 {len(new_replies)}개 수집 완료")
                    
                    # 페이지 진행상황 로그
                    self._logger.info(f"📄 페이지 {page_count}: {page_comments}개 댓글 수집")
                    self._logger.info(f"   📊 누적 통계: 총 {len(all_comments):,}개 댓글 ({total_threads_processed}개 스레드)")
                    
                    # 다음 페이지 확인
                    next_page_token = response.get('nextPageToken')
                    if not next_page_token:
                        self._logger.info("🎉 모든 댓글 및 대댓글 수집 완료!")
                        break
                    
                    # 대용량 수집시 중간 진행상황 표시
                    if page_count % 10 == 0:
                        self._logger.info(f"⏱️  진행상황: {page_count}페이지 완료, {len(all_comments):,}개 댓글 수집됨")
                    
                    break  # 성공시 재시도 루프 종료
                        
                except HttpError as e:
                    if self._handle_api_error(e, "댓글 수집"):
                        retry_count += 1
                        continue
                    else:
                        self._logger.error(f"API 요청 실패: {e}")
                        break
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        self._logger.error(f"수집 중 오류 (최대 재시도 초과): {e}")
                        break
                    
                    self._logger.warning(f"댓글 수집 재시도 {retry_count}/{max_retries}: {e}")
                    time.sleep(self.config.retry_delay * retry_count)
            
            # 재시도 한계 도달 또는 다음 페이지 없음
            if not next_page_token or retry_count >= max_retries:
                break
        
        # 최종 수집 결과 요약
        structure = self.analyze_comment_structure(all_comments)
        self._logger.info(f"🏁 비디오 {video_id} 수집 완료:")
        self._logger.info(f"   📊 총 댓글: {len(all_comments):,}개")
        self._logger.info(f"   🔝 최상위 댓글: {structure['top_level_comments']:,}개")
        self._logger.info(f"   💬 답글: {structure['replies']:,}개")
        self._logger.info(f"   🧵 답글 있는 스레드: {structure['threads_with_replies']:,}개")
        self._logger.info(f"   📈 스레드당 평균 답글: {structure['average_replies_per_thread']}")
        self._logger.info(f"   🏆 최대 답글 스레드: {structure['max_replies_per_thread']}개")
        
        return all_comments
    
    def analyze_comment_structure(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """댓글 구조 상세 분석"""
        analysis = {
            'total_comments': len(comments),
            'top_level_comments': 0,
            'replies': 0,
            'threads_with_replies': 0,
            'max_replies_per_thread': 0,
            'total_threads': 0,
            'average_replies_per_thread': 0,
            'reply_distribution': {},  # 답글 수별 스레드 분포
            'most_replied_thread': None,  # 가장 답글이 많은 스레드
            'total_likes': 0,
            'average_likes_per_comment': 0
        }
        
        if not comments:
            return analysis
        
        # 최상위 댓글들과 답글들 분리
        top_level = [c for c in comments if not c['is_reply']]
        replies = [c for c in comments if c['is_reply']]
        
        analysis['top_level_comments'] = len(top_level)
        analysis['replies'] = len(replies)
        analysis['total_threads'] = len(top_level)
        
        # 전체 좋아요 수 계산
        analysis['total_likes'] = sum(c['like_count'] for c in comments)
        analysis['average_likes_per_comment'] = round(analysis['total_likes'] / len(comments), 2) if comments else 0
        
        # 답글 분석
        if replies:
            threads_with_replies = set()
            reply_counts = {}
            
            for reply in replies:
                parent_id = reply['parent_id']
                threads_with_replies.add(parent_id)
                reply_counts[parent_id] = reply_counts.get(parent_id, 0) + 1
            
            analysis['threads_with_replies'] = len(threads_with_replies)
            analysis['max_replies_per_thread'] = max(reply_counts.values()) if reply_counts else 0
            analysis['average_replies_per_thread'] = round(len(replies) / len(top_level), 2) if top_level else 0
            
            # 답글 수별 분포 계산
            reply_distribution = {}
            for count in reply_counts.values():
                reply_distribution[count] = reply_distribution.get(count, 0) + 1
            analysis['reply_distribution'] = reply_distribution
            
            # 가장 답글이 많은 스레드 찾기
            if reply_counts:
                most_replied_parent = max(reply_counts.items(), key=lambda x: x[1])
                # 해당 최상위 댓글 찾기
                most_replied_comment = next((c for c in top_level if c['comment_id'] == most_replied_parent[0]), None)
                if most_replied_comment:
                    analysis['most_replied_thread'] = {
                        'comment_id': most_replied_comment['comment_id'],
                        'author': most_replied_comment['author'],
                        'text': most_replied_comment['text_original'][:100] + ('...' if len(most_replied_comment['text_original']) > 100 else ''),
                        'reply_count': most_replied_parent[1],
                        'like_count': most_replied_comment['like_count']
                    }
        
        return analysis
    
    # ==================== PRIVATE 메서드 ====================
    
    def _rate_limit(self):
        """API 호출 제한"""
        current_time = time.time()
        time_since_last = current_time - self._last_call_time
        
        if time_since_last < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - time_since_last)
        
        self._last_call_time = time.time()
    
    def _check_quota(self, cost: int = 1) -> bool:
        """할당량 확인 및 API 키 순환"""
        if self.quota_usage + cost > self.config.quota_limit_per_day:
            self._logger.warning(f"할당량 한계 도달: {self.quota_usage}/{self.config.quota_limit_per_day}")
            
            # API 키 변경 시도
            if self.config._change_api():
                # 새로운 API 키로 YouTube 클라이언트 재생성
                self.youtube = build('youtube', 'v3', developerKey=self.config.api_key)
                self.quota_usage = 0  # 할당량 리셋
                self._logger.info("새로운 API 키로 전환 완료")
                return True
            else:
                raise Exception(f"모든 API 키의 일일 할당량이 초과되었습니다.")
        return True
    
    def _handle_api_error(self, error: HttpError, operation: str):
        """API 오류 처리 및 키 순환"""
        if error.resp.status == 403:
            error_content = error.content.decode('utf-8') if hasattr(error, 'content') else str(error)
            if 'quotaExceeded' in error_content:
                self._logger.warning(f"{operation} 중 할당량 초과 감지")
                if self.config._change_api():
                    # 새로운 API 키로 YouTube 클라이언트 재생성
                    self.youtube = build('youtube', 'v3', developerKey=self.config.api_key)
                    self.quota_usage = 0
                    return True  # 재시도 가능
                else:
                    raise Exception("모든 API 키의 할당량이 초과되었습니다.")
        return False  # 재시도 불가
    
    def _extract_comment_data(self, item: Dict, video_id: str, is_reply: bool = False, parent_id: str = '') -> Dict:
        """댓글 데이터 추출 - 통합 버전"""
        if is_reply:
            snippet = item['snippet']
        else:
            snippet = item['snippet']['topLevelComment']['snippet']
        
        return {
            'comment_id': item['id'],
            'video_id': video_id,
            'author': snippet['authorDisplayName'],
            'author_channel_id': snippet.get('authorChannelId', {}).get('value', ''),
            'comment_text': snippet['textDisplay'],
            'text_original': snippet['textOriginal'],
            'like_count': snippet['likeCount'],
            'published_at': snippet['publishedAt'],
            'updated_at': snippet['updatedAt'],
            'reply_count': item['snippet'].get('totalReplyCount', 0) if not is_reply else 0,
            'is_reply': is_reply,
            'parent_id': parent_id,
            'reply_depth': 1 if is_reply and parent_id else 0
        }
    
    def _get_all_replies(self, parent_id: str, video_id: str) -> List[Dict]:
        """특정 댓글의 모든 답글 수집 (무제한)"""
        all_replies = []
        next_page_token = None
        max_retries = self.config.max_retries
        page_count = 0
        
        self._logger.debug(f"답글 수집 시작: 댓글 {parent_id}")
        
        while True:
            retry_count = 0
            while retry_count < max_retries:
                try:
                    self._check_quota(1)
                    self._rate_limit()
                    
                    request = self.youtube.comments().list(
                        part='snippet',
                        parentId=parent_id,
                        maxResults=100,  # 최대값 사용
                        pageToken=next_page_token if next_page_token else None
                    )
                    
                    response = request.execute()
                    self.quota_usage += 1
                    page_count += 1
                    
                    page_replies = 0
                    for item in response.get('items', []):
                        reply_data = self._extract_comment_data(item, video_id, is_reply=True, parent_id=parent_id)
                        all_replies.append(reply_data)
                        page_replies += 1
                    
                    if page_replies > 0:
                        self._logger.debug(f"답글 페이지 {page_count}: {page_replies}개 (총 {len(all_replies)}개)")
                    
                    next_page_token = response.get('nextPageToken')
                    if not next_page_token:
                        if len(all_replies) > 0:
                            self._logger.info(f"답글 수집 완료: 댓글 {parent_id} - 총 {len(all_replies)}개")
                        return all_replies
                    break  # 성공시 재시도 루프 종료
                        
                except HttpError as e:
                    if e.resp.status == 404:
                        self._logger.debug(f"댓글 {parent_id}의 답글을 찾을 수 없습니다.")
                        return all_replies
                    elif self._handle_api_error(e, "답글 수집"):
                        retry_count += 1
                        continue
                    else:
                        self._logger.error(f"답글 수집 실패: {e}")
                        return all_replies
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        self._logger.error(f"답글 수집 중 오류 (최대 재시도 초과): {e}")
                        return all_replies
                    
                    self._logger.warning(f"답글 수집 재시도 {retry_count}/{max_retries}: {e}")
                    time.sleep(self.config.retry_delay * retry_count)
        
        return all_replies