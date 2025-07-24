import os
import json
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pickle
import requests
from xml.etree import ElementTree

# .env 파일에서 환경 변수 로드
load_dotenv()

# API 키 및 OAuth 설정
API_KEY = os.getenv('YOUTUBE_API_KEY')
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

class YouTubeCaptionCollector:
    def __init__(self):
        self.youtube = None
        self.setup_youtube_client()
    
    def setup_youtube_client(self):
        """YouTube API 클라이언트 설정 (OAuth 인증 포함)"""
        creds = None
        
        # 저장된 토큰이 있는지 확인
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # 토큰이 없거나 유효하지 않으면 새로 인증
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # credentials.json 파일이 필요합니다
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # 토큰 저장
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.youtube = build('youtube', 'v3', credentials=creds)
    
    def get_video_info(self, video_id):
        """비디오 정보 가져오기 (API 키로 가능)"""
        youtube_api_key = build('youtube', 'v3', developerKey=API_KEY)
        
        request = youtube_api_key.videos().list(
            part='snippet,statistics,contentDetails',
            id=video_id
        )
        response = request.execute()
        
        if response['items']:
            return response['items'][0]
        return None
    
    def get_caption_list(self, video_id):
        """비디오의 자막 목록 가져오기 (OAuth 필요)"""
        try:
            request = self.youtube.captions().list(
                part='snippet',
                videoId=video_id
            )
            response = request.execute()
            return response.get('items', [])
        except Exception as e:
            print(f"자막 목록 가져오기 실패: {e}")
            return []
    
    def download_caption(self, caption_id, language='ko'):
        """특정 자막 다운로드"""
        try:
            request = self.youtube.captions().download(
                id=caption_id,
                tfmt='srt'  # srt, vtt, sbv 형식 지원
            )
            caption_content = request.execute()
            return caption_content
        except Exception as e:
            print(f"자막 다운로드 실패: {e}")
            return None
    
    def find_korean_auto_caption(self, video_id):
        """한글 자동생성 자막 찾기"""
        captions = self.get_caption_list(video_id)
        
        for caption in captions:
            snippet = caption['snippet']
            # 한글이고 자동생성된 자막 찾기
            if (snippet['language'] == 'ko' and 
                snippet['trackKind'] == 'asr'):  # asr = 자동음성인식
                return caption
        
        return None
    
    def collect_video_with_captions(self, video_id):
        """비디오 정보와 자막을 함께 수집"""
        print(f"비디오 ID {video_id} 처리 중...")
        
        # 1. 비디오 기본 정보 수집
        video_info = self.get_video_info(video_id)
        if not video_info:
            print("비디오 정보를 찾을 수 없습니다.")
            return None
        
        # 2. 한글 자동생성 자막 찾기
        korean_caption = self.find_korean_auto_caption(video_id)
        if not korean_caption:
            print("한글 자동생성 자막을 찾을 수 없습니다.")
            return {
                'video_info': video_info,
                'captions': None,
                'caption_text': None
            }
        
        # 3. 자막 다운로드
        caption_text = self.download_caption(korean_caption['id'])
        
        return {
            'video_info': video_info,
            'captions': korean_caption,
            'caption_text': caption_text
        }
    
    def extract_video_id_from_url(self, url):
        """YouTube URL에서 비디오 ID 추출"""
        if 'watch?v=' in url:
            return url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        else:
            return url  # 이미 비디오 ID인 경우

# 사용 예제
def main():
    collector = YouTubeCaptionCollector()
    
    # 비디오 URL 또는 ID
    video_url = "https://www.youtube.com/watch?v=VIDEO_ID_HERE"
    video_id = collector.extract_video_id_from_url(video_url)
    
    # 비디오 정보와 자막 수집
    result = collector.collect_video_with_captions(video_id)
    
    if result:
        print("=== 비디오 정보 ===")
        print(f"제목: {result['video_info']['snippet']['title']}")
        print(f"채널: {result['video_info']['snippet']['channelTitle']}")
        print(f"조회수: {result['video_info']['statistics']['viewCount']}")
        
        if result['caption_text']:
            print("\n=== 자막 내용 (처음 500자) ===")
            print(result['caption_text'][:500])
            
            # 자막을 파일로 저장
            with open(f"{video_id}_korean_captions.srt", "w", encoding="utf-8") as f:
                f.write(result['caption_text'])
            print(f"\n자막이 {video_id}_korean_captions.srt 파일로 저장되었습니다.")
        else:
            print("\n한글 자동생성 자막이 없습니다.")

if __name__ == "__main__":
    main()