"""
YouTube 단일 영상 메타데이터 추출기
Google API Client 라이브러리 사용
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate
from datetime import datetime
import re

class YouTubeVideoMetadata:
    def __init__(self, api_key):
        """
        YouTube 영상 메타데이터 추출기 초기화
        
        Args:
            api_key (str): YouTube Data API 키
        """
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
    
    def extract_video_id(self, url_or_id):
        """
        YouTube URL에서 영상 ID 추출 또는 ID 그대로 반환
        
        Args:
            url_or_id (str): YouTube URL 또는 영상 ID
            
        Returns:
            str: 영상 ID
        """
        # 이미 영상 ID인 경우
        if len(url_or_id) == 11 and not '/' in url_or_id:
            return url_or_id
        
        # YouTube URL에서 ID 추출
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        raise ValueError("올바른 YouTube URL 또는 영상 ID를 입력해주세요.")
    
    def get_video_metadata(self, video_url_or_id):
        """
        영상의 모든 메타데이터 추출
        
        Args:
            video_url_or_id (str): YouTube URL 또는 영상 ID
            
        Returns:
            dict: 완전한 영상 메타데이터
        """
        try:
            video_id = self.extract_video_id(video_url_or_id)
            
            # 모든 가능한 part 요청
            request = self.youtube.videos().list(
                part='snippet,statistics,contentDetails,status,recordingDetails,topicDetails',
                id=video_id
            )
            response = request.execute()
            
            if not response['items']:
                raise ValueError("영상을 찾을 수 없습니다. 영상 ID나 URL을 확인해주세요.")
            
            video = response['items'][0]
            
            # 메타데이터 추출 및 정리
            metadata = self._extract_basic_info(video)
            metadata.update(self._extract_snippet_info(video))
            metadata.update(self._extract_statistics(video))
            metadata.update(self._extract_content_details(video))
            metadata.update(self._extract_status_info(video))
            metadata.update(self._extract_topic_details(video))
            metadata.update(self._extract_recording_details(video))
            metadata.update(self._calculate_analytics(metadata))
            metadata.update(self._generate_urls(video_id))
            
            return metadata
            
        except HttpError as e:
            raise Exception(f"YouTube API 오류: {e}")
        except Exception as e:
            raise Exception(f"메타데이터 추출 중 오류 발생: {e}")
    
    def _extract_basic_info(self, video):
        """기본 정보 추출"""
        return {
            'video_id': video['id'],
            'etag': video.get('etag'),
            'kind': video.get('kind'),
        }
    
    def _extract_snippet_info(self, video):
        """snippet 정보 추출"""
        snippet = video.get('snippet', {})
        return {
            'title': snippet.get('title'),
            'description': snippet.get('description'),
            'channel_title': snippet.get('channelTitle'),
            'channel_id': snippet.get('channelId'),
            'published_at': snippet.get('publishedAt'),
            'category_id': snippet.get('categoryId'),
            'tags': snippet.get('tags', []),
            'default_language': snippet.get('defaultLanguage'),
            'default_audio_language': snippet.get('defaultAudioLanguage'),
            'live_broadcast_content': snippet.get('liveBroadcastContent'),
            'thumbnails': snippet.get('thumbnails', {}),
            'localized_title': snippet.get('localized', {}).get('title'),
            'localized_description': snippet.get('localized', {}).get('description'),
        }
    
    def _extract_statistics(self, video):
        """통계 정보 추출"""
        statistics = video.get('statistics', {})
        return {
            'view_count': int(statistics.get('viewCount', 0)),
            'like_count': int(statistics.get('likeCount', 0)),
            'comment_count': int(statistics.get('commentCount', 0)),
            'favorite_count': int(statistics.get('favoriteCount', 0)),
        }
    
    def _extract_content_details(self, video):
        """콘텐츠 세부정보 추출"""
        content_details = video.get('contentDetails', {})
        
        # 재생시간 처리
        duration_iso = content_details.get('duration', 'PT0S')
        duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
        
        # 지역 제한 정보
        region_restriction = content_details.get('regionRestriction', {})
        
        return {
            'duration_iso': duration_iso,
            'duration_seconds': int(duration_seconds),
            'duration_formatted': self._format_duration(duration_seconds),
            'dimension': content_details.get('dimension'),  # 2d, 3d
            'definition': content_details.get('definition'),  # hd, sd
            'caption': content_details.get('caption'),  # true/false
            'licensed_content': content_details.get('licensedContent'),
            'projection': content_details.get('projection'),  # rectangular, 360
            'has_custom_thumbnail': content_details.get('hasCustomThumbnail'),
            'content_rating': content_details.get('contentRating', {}),
            'allowed_regions': region_restriction.get('allowed', []),
            'blocked_regions': region_restriction.get('blocked', []),
        }
    
    def _extract_status_info(self, video):
        """상태 정보 추출"""
        status = video.get('status', {})
        return {
            'upload_status': status.get('uploadStatus'),
            'privacy_status': status.get('privacyStatus'),
            'license': status.get('license'),
            'embeddable': status.get('embeddable'),
            'public_stats_viewable': status.get('publicStatsViewable'),
            'made_for_kids': status.get('madeForKids'),
            'self_declared_made_for_kids': status.get('selfDeclaredMadeForKids'),
        }
    
    def _extract_topic_details(self, video):
        """주제/카테고리 정보 추출"""
        topic_details = video.get('topicDetails', {})
        return {
            'topic_ids': topic_details.get('topicIds', []),
            'topic_categories': topic_details.get('topicCategories', []),
            'relevant_topic_ids': topic_details.get('relevantTopicIds', []),
        }
    
    def _extract_recording_details(self, video):
        """촬영 정보 추출"""
        recording_details = video.get('recordingDetails', {})
        location = recording_details.get('location', {})
        
        return {
            'recording_date': recording_details.get('recordingDate'),
            'location_description': recording_details.get('locationDescription'),
            'location_latitude': location.get('latitude'),
            'location_longitude': location.get('longitude'),
            'location_altitude': location.get('altitude'),
        }
    
    def _calculate_analytics(self, metadata):
        """분석 지표 계산"""
        views = metadata.get('view_count', 0)
        likes = metadata.get('like_count', 0)
        comments = metadata.get('comment_count', 0)
        
        analytics = {}
        
        # 참여율 계산
        if views > 0:
            analytics['like_ratio'] = round((likes / views) * 100, 3)
            analytics['engagement_rate'] = round(((likes + comments) / views) * 100, 3)
        else:
            analytics['like_ratio'] = 0
            analytics['engagement_rate'] = 0
        
        # 업로드 후 경과 시간 및 일평균 조회수
        published_at = metadata.get('published_at')
        if published_at:
            try:
                published = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                now = datetime.now(published.tzinfo)
                days_since_upload = (now - published).days
                
                analytics['days_since_upload'] = days_since_upload
                analytics['upload_date'] = published.strftime('%Y-%m-%d')
                analytics['upload_time'] = published.strftime('%H:%M:%S')
                
                if days_since_upload > 0:
                    analytics['views_per_day'] = round(views / days_since_upload, 2)
                else:
                    analytics['views_per_day'] = views
            except:
                analytics['days_since_upload'] = None
                analytics['views_per_day'] = None
        
        return analytics
    
    def _generate_urls(self, video_id):
        """관련 URL 생성"""
        return {
            'video_url': f"https://www.youtube.com/watch?v={video_id}",
            'short_url': f"https://youtu.be/{video_id}",
            'embed_url': f"https://www.youtube.com/embed/{video_id}",
            'thumbnail_maxres': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            'thumbnail_high': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            'thumbnail_medium': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            'thumbnail_default': f"https://img.youtube.com/vi/{video_id}/default.jpg",
        }
    
    def _format_duration(self, seconds):
        """초를 시:분:초 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def print_metadata_summary(self, video_url_or_id):
        """메타데이터 요약 출력"""
        try:
            metadata = self.get_video_metadata(video_url_or_id)
            
            print("=" * 60)
            print("📹 YouTube 영상 메타데이터")
            print("=" * 60)
            
            print(f"📌 제목: {metadata['title']}")
            print(f"🎬 채널: {metadata['channel_title']}")
            print(f"⏱️  재생시간: {metadata['duration_formatted']}")
            print(f"👀 조회수: {metadata['view_count']:,}")
            print(f"👍 좋아요: {metadata['like_count']:,}")
            print(f"💬 댓글: {metadata['comment_count']:,}")
            print(f"📅 업로드: {metadata.get('upload_date', 'N/A')}")
            print(f"🔗 URL: {metadata['video_url']}")
            
            print(f"\n📊 분석 지표:")
            print(f"   • 좋아요 비율: {metadata.get('like_ratio', 0):.3f}%")
            print(f"   • 참여율: {metadata.get('engagement_rate', 0):.3f}%")
            print(f"   • 업로드 후 경과일: {metadata.get('days_since_upload', 'N/A')}")
            print(f"   • 일평균 조회수: {metadata.get('views_per_day', 'N/A')}")
            
            print(f"\n🎥 기술 정보:")
            print(f"   • 화질: {metadata.get('definition', 'N/A').upper()}")
            print(f"   • 자막: {'있음' if metadata.get('caption') == 'true' else '없음'}")
            print(f"   • 공개 설정: {metadata.get('privacy_status', 'N/A')}")
            print(f"   • 임베드 가능: {'예' if metadata.get('embeddable') else '아니오'}")
            
            if metadata.get('tags'):
                print(f"\n🏷️  태그: {', '.join(metadata['tags'][:10])}")
                if len(metadata['tags']) > 10:
                    print(f"   ... 외 {len(metadata['tags']) - 10}개")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")


# 사용 예제
def main():
    import os
    import json
    import dotenv
    
    # API 키 설정
    dotenv.load_dotenv()
    API_KEY = os.getenv('YOUTUBE_API_KEY')
    
    if not API_KEY:
        print("❌ YouTube API 키가 설정되지 않았습니다.")
        print("환경변수 YOUTUBE_API_KEY를 설정하거나 아래 코드에서 직접 입력하세요.")
        # API_KEY = "여기에_API_키_입력"
        return
    
    # 메타데이터 추출기 생성
    extractor = YouTubeVideoMetadata(API_KEY)
    
    # 테스트할 영상
    test_video = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    print(f"🔍 분석 대상: {test_video}")
    print("=" * 80)
    
    try:
        # 전체 메타데이터 가져오기
        full_data = extractor.get_video_metadata(test_video)
        
        print("📹 YouTube 영상 전체 메타데이터")
        print("=" * 80)
        
        # 기본 정보
        print("\n🔹 기본 정보:")
        basic_fields = ['video_id', 'etag', 'kind']
        for field in basic_fields:
            if field in full_data and full_data[field]:
                print(f"   {field}: {full_data[field]}")
        
        # 영상 정보
        print("\n🔹 영상 정보:")
        video_fields = ['title', 'channel_title', 'channel_id', 'published_at', 'category_id']
        for field in video_fields:
            if field in full_data and full_data[field]:
                print(f"   {field}: {full_data[field]}")
        
        # 통계
        print("\n🔹 통계:")
        stats_fields = ['view_count', 'like_count', 'comment_count', 'favorite_count']
        for field in stats_fields:
            if field in full_data and full_data[field] is not None:
                print(f"   {field}: {full_data[field]:,}")
        
        # 콘텐츠 세부사항
        print("\n🔹 콘텐츠 세부사항:")
        content_fields = ['duration_formatted', 'duration_seconds', 'dimension', 'definition', 
                            'caption', 'licensed_content', 'projection', 'has_custom_thumbnail']
        for field in content_fields:
            if field in full_data and full_data[field] is not None:
                print(f"   {field}: {full_data[field]}")
        
        # 상태 정보
        print("\n🔹 상태 정보:")
        status_fields = ['upload_status', 'privacy_status', 'license', 'embeddable', 
                        'public_stats_viewable', 'made_for_kids', 'self_declared_made_for_kids']
        for field in status_fields:
            if field in full_data and full_data[field] is not None:
                print(f"   {field}: {full_data[field]}")
        
        # 언어 및 지역화
        print("\n🔹 언어 및 지역화:")
        lang_fields = ['default_language', 'default_audio_language', 'localized_title', 'localized_description']
        for field in lang_fields:
            if field in full_data and full_data[field]:
                if field in ['localized_title', 'localized_description']:
                    # 긴 텍스트는 일부만 출력
                    text = str(full_data[field])[:100] + "..." if len(str(full_data[field])) > 100 else full_data[field]
                    print(f"   {field}: {text}")
                else:
                    print(f"   {field}: {full_data[field]}")
        
        # 분석 지표
        print("\n🔹 분석 지표:")
        analytics_fields = ['like_ratio', 'engagement_rate', 'days_since_upload', 'views_per_day', 
                            'upload_date', 'upload_time']
        for field in analytics_fields:
            if field in full_data and full_data[field] is not None:
                print(f"   {field}: {full_data[field]}")
        
        # 주제/카테고리
        print("\n🔹 주제/카테고리:")
        topic_fields = ['topic_ids', 'topic_categories', 'relevant_topic_ids']
        for field in topic_fields:
            if field in full_data and full_data[field]:
                if isinstance(full_data[field], list) and len(full_data[field]) > 0:
                    if len(full_data[field]) <= 5:
                        print(f"   {field}: {full_data[field]}")
                    else:
                        print(f"   {field}: {full_data[field][:5]}... (총 {len(full_data[field])}개)")
                else:
                    print(f"   {field}: {full_data[field]}")
        
        # 위치 정보
        print("\n🔹 위치 정보:")
        location_fields = ['recording_date', 'location_description', 'location_latitude', 
                            'location_longitude', 'location_altitude']
        has_location = False
        for field in location_fields:
            if field in full_data and full_data[field] is not None:
                print(f"   {field}: {full_data[field]}")
                has_location = True
        if not has_location:
            print("   위치 정보 없음")
        
        # 지역 제한
        print("\n🔹 지역 제한:")
        if full_data.get('blocked_regions'):
            if len(full_data['blocked_regions']) <= 10:
                print(f"   blocked_regions: {full_data['blocked_regions']}")
            else:
                print(f"   blocked_regions: {full_data['blocked_regions'][:10]}... (총 {len(full_data['blocked_regions'])}개)")
        elif full_data.get('allowed_regions'):
            if len(full_data['allowed_regions']) <= 10:
                print(f"   allowed_regions: {full_data['allowed_regions']}")
            else:
                print(f"   allowed_regions: {full_data['allowed_regions'][:10]}... (총 {len(full_data['allowed_regions'])}개)")
        else:
            print("   지역 제한 없음")
        
        # URL 정보
        print("\n🔹 URL 정보:")
        url_fields = ['video_url', 'short_url', 'embed_url', 'thumbnail_maxres', 
                        'thumbnail_high', 'thumbnail_medium', 'thumbnail_default']
        for field in url_fields:
            if field in full_data and full_data[field]:
                print(f"   {field}: {full_data[field]}")
        
        # 태그
        print("\n🔹 태그:")
        if full_data.get('tags'):
            if len(full_data['tags']) <= 10:
                print(f"   tags: {full_data['tags']}")
            else:
                print(f"   tags: {full_data['tags'][:10]}... (총 {len(full_data['tags'])}개)")
        else:
            print("   태그 없음")
        
        # 설명 (일부만)
        print("\n🔹 설명 (처음 200자):")
        description = full_data.get('description', '')
        if description:
            print(f"   description: {description[:200]}...")
        else:
            print("   설명 없음")
        
        # 썸네일 정보
        print("\n🔹 썸네일 정보:")
        thumbnails = full_data.get('thumbnails', {})
        if thumbnails:
            for quality, thumbnail in thumbnails.items():
                if isinstance(thumbnail, dict) and 'url' in thumbnail:
                    print(f"   {quality}: {thumbnail['url']} ({thumbnail.get('width', '?')}x{thumbnail.get('height', '?')})")
        else:
            print("   썸네일 정보 없음")
        
        # 콘텐츠 등급
        print("\n🔹 콘텐츠 등급:")
        content_rating = full_data.get('content_rating', {})
        if content_rating:
            for rating_system, rating in content_rating.items():
                print(f"   {rating_system}: {rating}")
        else:
            print("   콘텐츠 등급 정보 없음")
        
        # 라이브 방송 관련
        print("\n🔹 라이브 방송:")
        live_content = full_data.get('live_broadcast_content')
        if live_content:
            print(f"   live_broadcast_content: {live_content}")
            print(f"   is_live: {live_content == 'live'}")
            print(f"   is_upcoming: {live_content == 'upcoming'}")
        else:
            print("   일반 업로드 영상")
        
        print("\n" + "=" * 80)
        print(f"✅ 총 {len([k for k, v in full_data.items() if v is not None and v != ''])}개의 메타데이터 추출 완료")
        
        # JSON 형태로도 출력 (선택사항)
        print(f"\n📄 JSON 형태 메타데이터 (파일로 저장 가능):")
        print("-" * 40)
        # 일부 필드만 JSON으로 출력 (너무 길어지지 않도록)
        json_data = {k: v for k, v in full_data.items() 
                    if k not in ['description', 'thumbnails'] and v is not None}
        print(json.dumps(json_data, indent=2, ensure_ascii=False)[:1000] + "...")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()