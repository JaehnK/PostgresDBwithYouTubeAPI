# YouTube Data Collection System

YouTube API를 활용한 체계적인 데이터 수집 및 분석 시스템입니다. 채널 정보, 영상 메타데이터, 자막, 댓글을 PostgreSQL 데이터베이스에 저장하고 관리합니다.

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![YouTube API](https://img.shields.io/badge/API-YouTube%20Data%20v3-red.svg)](https://developers.google.com/youtube/v3)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [프로젝트 구조](#프로젝트-구조)
- [데이터베이스 스키마](#데이터베이스-스키마)
- [설치 방법](#설치-방법)
- [환경 설정](#환경-설정)
- [사용법](#사용법)
- [API 할당량 관리](#api-할당량-관리)
- [데이터 분석 예시](#데이터-분석-예시)
- [트러블슈팅](#트러블슈팅)

## 개요

이 시스템은 YouTube Data API v3를 사용하여 다음과 같은 데이터를 자동으로 수집하고 PostgreSQL 데이터베이스에 저장합니다:

- **채널 정보**: 구독자 수, 영상 수, 총 조회수 등
- **영상 메타데이터**: 제목, 조회수, 좋아요, 댓글 수, 참여도 지표
- **자막 데이터**: 타임스탬프 포함 자막 파일
- **댓글 데이터**: 댓글 및 대댓글의 구조화된 데이터

## 주요 기능

- **채널 데이터 수집**: `YouTubeWorkFlow.process_channel_information()`
- **영상 정보 수집**: 메타데이터, 자막, 댓글을 통합 처리
- **댓글 구조 분석**: 대댓글 관계 및 참여도 분석
- **자동 지표 계산**: 좋아요 비율, 참여도(engagement rate)
- **할당량 관리**: API 키 자동 교체로 연속 수집 지원
- **PostgreSQL 저장**: 중복 처리 및 업데이트 지원 (UPSERT)
- **아시아/서울 시간대**: 모든 타임스탬프 한국 시간 기준
- **다중 언어 자막**: 한국어, 영어, 일본어 등 다국어 자막 지원
- **인터페이스 기반 설계**: 유지보수성과 확장성을 고려한 아키텍처

## 프로젝트 구조

```
PostgresDBwithYouTubeAPI/
├── main.py                     # 메인 실행 파일
├── requirements.txt            # 의존성 패키지 목록
├── cookies.txt                # YouTube 쿠키 (Firefox 확장프로그램으로 생성)
├── .gitignore                  # Git 무시 파일 목록
├── srcs/                       # 소스 코드 디렉토리
│   ├── dao/
│   │   └── YouTubeDao.py       # 데이터베이스 연결 및 CRUD 작업
│   ├── services/
│   │   ├── YouTubeAPIClient.py         # YouTube API 클라이언트
│   │   ├── YouTubeCommentCollector.py  # 댓글 수집 서비스
│   │   ├── YTDLPDownLoader.py          # 자막 다운로더
│   │   └── SubtitleProcessor.py        # 자막 처리
│   ├── manager/
│   │   ├── VideoMetaDataExtractor.py   # 영상 메타데이터 추출
│   │   ├── ChannelMetadataExtractor.py # 채널 메타데이터 추출
│   │   └── SubtitleManager.py          # 자막 관리
│   ├── interfaces/             # 인터페이스 정의
│   │   ├── IYouTubeAPIClient.py
│   │   ├── ICommentCollector.py
│   │   ├── ISubtitleDownloader.py
│   │   └── IYouTubeDao.py
│   ├── utils/
│   │   └── YoutubeUtils.py     # 유틸리티 함수
│   ├── YouTubeConfig.py        # 설정 관리
│   ├── YouTubeServiceFactory.py # 서비스 팩토리
│   └── YouTubeWorkFlow.py      # 메인 워크플로우
└── RubbishBin/                 # 테스트 및 임시 파일
    └── (개발 중 생성된 자막 파일들)
```

## 데이터베이스 스키마

### Channel 테이블
```sql
CREATE TABLE channel (
    channel_id VARCHAR PRIMARY KEY,    -- 유튜브 채널 고유 ID
    customUrl VARCHAR,                 -- @채널명 형태 URL
    title VARCHAR,                     -- 채널명
    country VARCHAR,                   -- 국가 코드 (예: KR)
    subscriberCount BIGINT,            -- 구독자 수
    videoCount BIGINT,                 -- 총 영상 수
    viewCount BIGINT,                  -- 총 조회수
    collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Videos 테이블
```sql
CREATE TABLE videos (
    video_id VARCHAR PRIMARY KEY,      -- 유튜브 영상 고유 ID
    channel_id VARCHAR,                -- 채널 ID (FK)
    title VARCHAR,                     -- 영상 제목
    view_count BIGINT,                 -- 조회수
    like_count BIGINT,                 -- 좋아요 수
    comment_count BIGINT,              -- 댓글 수
    duration_formatted BIGINT,         -- 재생 시간
    script VARCHAR,                    -- 자막 텍스트
    script_timestamp VARCHAR,          -- 타임스탬프 포함 자막
    like_ratio FLOAT,                  -- 좋아요 비율
    engagement_rate FLOAT,             -- 참여도
    collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Comments 테이블
```sql
CREATE TABLE comments (
    comment_id VARCHAR PRIMARY KEY,    -- 댓글 고유 ID
    video_id VARCHAR,                  -- 영상 ID (FK)
    author VARCHAR,                    -- 작성자명
    comment_text VARCHAR,              -- 댓글 내용
    like_count BIGINT,                 -- 좋아요 수
    is_reply BOOLEAN,                  -- 대댓글 여부
    parent_id VARCHAR,                 -- 부모 댓글 ID
    collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 설치 방법

### 사전 요구사항
- Python 3.8+
- PostgreSQL 12+
- YouTube Data API v3 키
- Firefox 브라우저 (쿠키 추출용)

### 설치 단계

1. **저장소 클론**
```bash
git clone https://github.com/your-username/PostgresDBwithYouTubeAPI.git
cd PostgresDBwithYouTubeAPI
```

2. **가상환경 설정**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

3. **의존성 설치**
```bash
pip install -r requirements.txt
```

4. **PostgreSQL 데이터베이스 생성**
```sql
CREATE DATABASE youtube_data;
CREATE USER youtube_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE youtube_data TO youtube_user;
```

5. **YouTube 쿠키 설정**
   
   자막 다운로드를 위해 YouTube 쿠키가 필요합니다:
   
   a. Firefox에서 [Cookies.txt 확장 프로그램](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) 설치
   
   b. YouTube에 로그인한 상태로 확장 프로그램을 통해 쿠키 내보내기
   
   c. 내보낸 `cookies.txt` 파일을 프로젝트 루트 디렉토리에 배치

## 환경 설정

`.env` 파일을 생성하고 다음 정보를 입력하세요:

```env
# YouTube API 설정
YOUTUBE_API_KEY=your_youtube_api_key_here
YOUTUBE_API_KEY_2=backup_api_key_here

# PostgreSQL 설정
DB_HOST=localhost
DB_PORT=5432
DB_NAME=youtube_data
DB_USER=youtube_user
DB_PASSWORD=your_password

# 출력 디렉토리
OUTPUT_DIR=./output
```

### 데이터베이스 초기화

```python
from srcs.dao.YouTubeDao import YouTubeDBSetup

# 테이블 생성
db_setup = YouTubeDBSetup()
db_setup.create_tables()
```

## 사용법

### 1. 기본 설정

```python
from srcs.YouTubeConfig import YouTubeConfig
from srcs.YouTubeWorkFlow import YouTubeWorkflow

# 설정 로드
config = YouTubeConfig()
workflow = YouTubeWorkflow(config)
```

### 2. 단일 영상 전체 처리

```python
# 영상 URL로 모든 데이터 수집 (메타데이터 + 자막 + 댓글)
video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

options = {
    'include_comments': True,      # 댓글 수집 포함
    'include_raw_comments': True,  # 원본 댓글 데이터 포함
    'output_dir': './subtitles',   # 자막 저장 경로
    'languages': ['ko', 'en'],     # 자막 언어
    'auto_subs': True              # 자동 생성 자막 포함
}

result = workflow.process_single_video(video_url, options)

print(f"처리 결과: {result['success']}")
print(f"댓글 수: {result['comments']['total_comments']}")
```

### 3. 채널 정보 수집

```python
# 채널 핸들러로 채널 정보 수집
channel_handler = "@channel_name"
result = workflow.process_channel_information(channel_handler)

print(f"채널: {result['metadata']['title']}")
print(f"구독자: {result['metadata']['subscriberCount']:,}명")
```

### 4. 메타데이터만 추출

```python
# 영상 메타데이터만 필요한 경우
metadata = workflow.extract_metadata_only(video_url)
print(f"제목: {metadata['title']}")
print(f"조회수: {metadata['view_count']:,}")
```

### 5. 자막만 다운로드

```python
# 자막 파일만 다운로드
subtitle_options = {
    'output_dir': './subtitles',
    'languages': ['ko'],
    'auto_subs': False
}

subtitles = workflow.download_subtitles_only(video_url, subtitle_options)
print(f"자막 파일: {subtitles['text_files']}")
```

### 6. 데이터베이스 직접 조회

```python
from srcs.dao.YouTubeDao import YouTubeDBSetup

db = YouTubeDBSetup()

# 저장된 데이터 통계
stats = db.get_data_count()
print(f"총 채널: {stats['channels']:,}개")
print(f"총 영상: {stats['videos']:,}개")
print(f"총 댓글: {stats['comments']:,}개")

# 특정 영상의 댓글 조회
comments = db.get_comments_by_video_id("dQw4w9WgXcQ")
print(f"댓글 수: {len(comments)}")

# 영상 메타데이터 조회
metadata = db.get_video_metadata("dQw4w9WgXcQ")
print(f"참여도: {metadata['engagement_rate']:.2f}%")
```

## API 할당량 관리

시스템은 자동으로 API 할당량을 관리합니다:

```python
# YouTubeConfig에서 여러 API 키 설정
api_keys = [
    "your_primary_api_key",
    "your_secondary_api_key",
    "your_backup_api_key"
]

# 할당량 초과 시 자동으로 다음 키로 전환
# HTTP 403 (quotaExceeded) 에러 발생 시 자동 처리
```

**할당량 모니터링:**
- 일일 할당량: 10,000 units
- 영상 메타데이터: 1 unit
- 댓글 수집: 1 unit per page
- 채널 정보: 1 unit

## 데이터 분석 예시

### 채널별 평균 참여도 분석
```sql
SELECT 
    channel_title,
    COUNT(*) as video_count,
    AVG(engagement_rate) as avg_engagement,
    AVG(view_count) as avg_views
FROM videos 
GROUP BY channel_title 
ORDER BY avg_engagement DESC
LIMIT 10;
```

### 시간대별 영상 업로드 패턴
```sql
SELECT 
    EXTRACT(HOUR FROM published_at::timestamp) as upload_hour,
    COUNT(*) as video_count,
    AVG(view_count) as avg_views
FROM videos
GROUP BY upload_hour
ORDER BY upload_hour;
```

### 댓글 참여도가 높은 영상
```sql
SELECT 
    v.title,
    v.view_count,
    v.comment_count,
    v.engagement_rate,
    COUNT(c.comment_id) as actual_comments
FROM videos v
LEFT JOIN comments c ON v.video_id = c.video_id
GROUP BY v.video_id, v.title, v.view_count, v.comment_count, v.engagement_rate
ORDER BY v.engagement_rate DESC
LIMIT 20;
```

## 트러블슈팅

### 일반적인 문제들

**1. API 할당량 초과**
```
해결: 추가 API 키를 .env에 등록하고 자동 전환 기능 사용
```

**2. PostgreSQL 연결 오류**
```
해결: DB 설정 확인 및 PostgreSQL 서비스 상태 점검
```

**3. 자막 다운로드 실패**
```
해결: 영상에 자막이 없거나 비공개 상태인지 확인
```

**4. 댓글 수집 제한**
```
해결: 댓글이 비활성화된 영상이거나 연령 제한 영상
```

### 로그 확인
```python
import logging
logging.basicConfig(level=logging.INFO)

# 워크플로우 실행 시 자세한 로그 출력
```

### 쿠키 관련 문제
**5. 자막 다운로드 시 403 에러**
```
해결: cookies.txt 파일이 최신인지 확인하고 Firefox에서 YouTube 재로그인 후 쿠키 재생성
```

**6. 쿠키 파일 포맷 에러**
```
해결: cookies.txt 확장프로그램을 통해 올바른 Netscape 포맷으로 쿠키 추출
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.

## 주의사항

- YouTube API 사용 정책을 준수해주세요
- 개인정보 보호를 위해 댓글 데이터 사용 시 주의하세요
- 대량 수집 시 서버 리소스를 모니터링하세요
- 타임존이 Asia/Seoul로 설정되어 있습니다

## 참고 자료

- [YouTube Data API v3 문서](https://developers.google.com/youtube/v3)
- [psycopg2 문서](https://www.psycopg.org/docs/)
- [YouTube API 사용 정책](https://developers.google.com/youtube/terms/api-services-terms-of-service)

---

이 프로젝트가 도움이 되셨다면 별표를 눌러주세요!
