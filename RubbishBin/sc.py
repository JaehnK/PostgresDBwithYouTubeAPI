import os
import json
import subprocess
import re
from dotenv import load_dotenv
from googleapiclient.discovery import build

# .env 파일에서 환경 변수 로드
load_dotenv()

# API 키 설정 (비디오 정보용)
API_KEY = os.getenv('YOUTUBE_API_KEY')

class YTDLPCaptionCollector:
    def __init__(self):
        # YouTube API 클라이언트 (비디오 정보용)
        self.youtube = build('youtube', 'v3', developerKey=API_KEY)
        
        # yt-dlp 설치 확인
        if not self.check_ytdlp():
            print("yt-dlp를 설치해주세요: pip install yt-dlp")
            exit(1)
    
    def check_ytdlp(self):
        """yt-dlp 설치 확인"""
        try:
            subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_video_info(self, video_id):
        """YouTube API로 비디오 정보 가져오기"""
        try:
            request = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            )
            response = request.execute()
            
            if response['items']:
                return response['items'][0]
            return None
        except Exception as e:
            print(f"비디오 정보 가져오기 실패: {e}")
            return None
    
    def list_available_subtitles(self, video_url):
        """사용 가능한 자막 목록 확인"""
        try:
            cmd = [
                'yt-dlp',
                '--list-subs',
                '--no-warnings',
                video_url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"자막 목록 확인 실패: {result.stderr}")
                return None
        except Exception as e:
            print(f"자막 목록 확인 오류: {e}")
            return None
    
    def download_subtitles(self, video_url, output_dir="./captions", languages=['ko'], auto_subs=True):
        """자막 다운로드"""
        try:
            # 출력 디렉토리 생성
            timestamp_dir = os.path.join(output_dir, "timestamp")
            text_only_dir = os.path.join(output_dir, "text_only")
            os.makedirs(timestamp_dir, exist_ok=True)
            os.makedirs(text_only_dir, exist_ok=True)
            
            # 기본 명령어 (timestamp 폴더에 SRT 파일 저장)
            cmd = [
                'yt-dlp',
                '--skip-download',  # 비디오는 다운로드하지 않음
                '--sub-format', 'srt',  # SRT 형식
                '--output', f'{timestamp_dir}/%(id)s.%(ext)s',  # 비디오ID.srt 형식
                video_url
            ]
            
            # 자막 옵션 추가
            if auto_subs:
                cmd.extend(['--write-auto-subs'])  # 자동생성 자막
            cmd.extend(['--write-subs'])  # 수동 자막
            
            # 언어 지정
            if languages:
                cmd.extend(['--sub-langs', ','.join(languages)])
            
            print(f"실행 명령어: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("자막 다운로드 성공!")
                
                # 다운로드된 SRT 파일들을 찾아서 텍스트 파일로 변환
                self.convert_srt_to_text(timestamp_dir, text_only_dir)
                
                return True
            else:
                print(f"자막 다운로드 실패: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"자막 다운로드 오류: {e}")
            return False
    
    def download_korean_subtitles_only(self, video_url, output_dir="./captions"):
        """한글 자막만 다운로드"""
        return self.download_subtitles(
            video_url, 
            output_dir, 
            languages=['ko'], 
            auto_subs=True
        )
    
    def download_all_available_subtitles(self, video_url, output_dir="./captions"):
        """모든 사용 가능한 자막 다운로드"""
        return self.download_subtitles(
             video_url, 
            output_dir, 
            languages=[], 
            auto_subs=True
        )
    
    def get_video_info_with_ytdlp(self, video_url):
        """yt-dlp로 비디오 정보 가져오기 (API 키 없이도 가능)"""
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-warnings',
                video_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                print(f"비디오 정보 가져오기 실패: {result.stderr}")
                return None
        except Exception as e:
            print(f"비디오 정보 가져오기 오류: {e}")
            return None
    
    def read_subtitle_file(self, file_path):
        """자막 파일 읽기"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"자막 파일 읽기 실패: {e}")
            return None
    
    def extract_text_from_srt(self, srt_content):
        """SRT 파일에서 텍스트만 추출"""
        if not srt_content:
            return ""
        
        # SRT 형식에서 타임스탬프와 번호를 제거하고 텍스트만 추출
        lines = srt_content.split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # 번호나 타임스탬프가 아닌 실제 텍스트 라인만 추출
            if line and not line.isdigit() and '-->' not in line:
                text_lines.append(line)
        
        return ' '.join(text_lines)
    
    def convert_srt_to_text(self, timestamp_dir, text_only_dir):
        """SRT 파일을 순수 텍스트 파일로 변환"""
        try:
            for filename in os.listdir(timestamp_dir):
                if filename.endswith('.srt'):
                    srt_path = os.path.join(timestamp_dir, filename)
                    
                    # SRT 파일 읽기
                    srt_content = self.read_subtitle_file(srt_path)
                    if srt_content:
                        # 텍스트만 추출
                        text_only = self.extract_text_from_srt(srt_content)
                        
                        # 파일명을 비디오ID.txt로 변경
                        video_id = filename.replace('.srt', '').replace('.ko', '').replace('.en', '')
                        # 자동생성 자막의 경우 .ko.srt 형식이므로 처리
                        if '.ko' in filename:
                            video_id = filename.split('.ko')[0]
                        elif '.en' in filename:
                            video_id = filename.split('.en')[0]
                        else:
                            video_id = filename.replace('.srt', '')
                        
                        text_filename = f"{video_id}.txt"
                        text_path = os.path.join(text_only_dir, text_filename)
                        
                        # 텍스트 파일로 저장
                        with open(text_path, 'w', encoding='utf-8') as f:
                            f.write(text_only)
                        
                        print(f"텍스트 파일 생성: {text_filename}")
                        
        except Exception as e:
            print(f"텍스트 변환 오류: {e}")
    
    def find_downloaded_subtitle_files(self, output_dir="./captions"):
        """다운로드된 자막 파일 찾기"""
        timestamp_dir = os.path.join(output_dir, "timestamp")
        text_only_dir = os.path.join(output_dir, "text_only")
        
        subtitle_files = {
            'timestamp': [],
            'text_only': []
        }
        
        # timestamp 폴더의 SRT 파일들
        if os.path.exists(timestamp_dir):
            for file in os.listdir(timestamp_dir):
                if file.endswith('.srt') or file.endswith('.vtt'):
                    subtitle_files['timestamp'].append(os.path.join(timestamp_dir, file))
        
        # text_only 폴더의 TXT 파일들
        if os.path.exists(text_only_dir):
            for file in os.listdir(text_only_dir):
                if file.endswith('.txt'):
                    subtitle_files['text_only'].append(os.path.join(text_only_dir, file))
        
        return subtitle_files
    
    def extract_video_id_from_url(self, url):
        """YouTube URL에서 비디오 ID 추출"""
        if 'watch?v=' in url:
            return url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        else:
            return url
    
    def collect_video_with_captions(self, video_url, output_dir="./captions"):
        """비디오 정보와 자막을 함께 수집"""
        video_id = self.extract_video_id_from_url(video_url)
        print(f"비디오 ID {video_id} 처리 중...")
        
        # 1. 비디오 기본 정보 수집 (YouTube API 또는 yt-dlp)
        video_info = None
        if API_KEY:
            video_info = self.get_video_info(video_id)
        
        if not video_info:
            print("YouTube API로 정보 가져오기 실패. yt-dlp로 시도합니다...")
            video_info = self.get_video_info_with_ytdlp(video_url)
        
        if video_info:
            if 'snippet' in video_info:  # YouTube API 형식
                title = video_info['snippet']['title']
                channel = video_info['snippet']['channelTitle']
            else:  # yt-dlp 형식
                title = video_info.get('title', 'Unknown')
                channel = video_info.get('uploader', 'Unknown')
            
            print(f"제목: {title}")
            print(f"채널: {channel}")
        
        # 2. 사용 가능한 자막 확인
        print("\n사용 가능한 자막 확인 중...")
        subtitle_list = self.list_available_subtitles(video_url)
        if subtitle_list:
            print(subtitle_list)
        
        # 3. 한글 자막 다운로드 시도
        print("\n한글 자막 다운로드 중...")
        korean_success = self.download_korean_subtitles_only(video_url, output_dir)
        
        # 4. 한글 자막이 없으면 모든 자막 다운로드
        if not korean_success:
            print("한글 자막이 없어 모든 사용 가능한 자막을 다운로드합니다...")
            self.download_all_available_subtitles(video_url, output_dir)
        
        # 5. 다운로드된 자막 파일 확인
        subtitle_files = self.find_downloaded_subtitle_files(output_dir)
        
        result = {
            'video_info': video_info,
            'subtitle_files': subtitle_files,
            'korean_success': korean_success
        }
        
        # 6. 자막 파일 내용 읽기 (첫 번째 텍스트 파일)
        if subtitle_files['text_only']:
            first_text_file = subtitle_files['text_only'][0]
            text_content = self.read_subtitle_file(first_text_file)
            if text_content:
                result['text_content'] = text_content
        
        return result

# 사용 예제
def main():
    collector = YTDLPCaptionCollector()
    
    # 테스트할 비디오 URL
    video_url = "https://www.youtube.com/watch?v=4BF-y27sB7I"
    
    # 비디오 정보와 자막 수집
    result = collector.collect_video_with_captions(video_url)
    
    if result:
        print("\n=== 수집 결과 ===")
        print(f"타임스탬프 자막: {len(result['subtitle_files']['timestamp'])}개")
        print(f"텍스트 파일: {len(result['subtitle_files']['text_only'])}개")
        
        print("\n타임스탬프 자막 파일:")
        for file in result['subtitle_files']['timestamp']:
            print(f"- {os.path.basename(file)}")
        
        print("\n텍스트 파일:")
        for file in result['subtitle_files']['text_only']:
            print(f"- {os.path.basename(file)}")
        
        if 'text_content' in result:
            print(f"\n=== 자막 내용 (처음 500자) ===")
            print(result['text_content'][:500])
        
        print(f"\n파일 구조:")
        print(f"./captions/timestamp/ - SRT 파일 (타임스탬프 포함)")
        print(f"./captions/text_only/ - TXT 파일 (순수 텍스트)")
        print(f"파일명: 비디오ID.srt, 비디오ID.txt")

if __name__ == "__main__":
    main()