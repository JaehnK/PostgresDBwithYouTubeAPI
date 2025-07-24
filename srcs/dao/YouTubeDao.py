import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
import os  
from datetime import datetime
import json 
from dotenv import load_dotenv

class YouTubeDBSetup:
    def __init__(self):
        load_dotenv()
        # 데이터베이스 연결 정보
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'port': os.getenv('DB_PORT', '5432')
        }
    
    def create_tables(self):
        """테이블 생성 및 초기 설정"""
        
        # 테이블 생성 SQL
        create_tables_sql = """
        -- 타임존 설정
        SET timezone = 'Asia/Seoul';
        
        -- 1. Channel 테이블 생성
        CREATE TABLE IF NOT EXISTS channel (
            channel_id VARCHAR NOT NULL PRIMARY KEY,
            customUrl VARCHAR,
            title VARCHAR,
            country VARCHAR,
            description VARCHAR,
            published_at VARCHAR,
            etag VARCHAR,
            hiddenSubscriberCount BOOLEAN,
            subscriberCount BIGINT,
            videoCount BIGINT,
            viewCount BIGINT,
            thumbnail_url VARCHAR,
            collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 2. Videos 테이블 생성
        CREATE TABLE IF NOT EXISTS videos (
            video_id VARCHAR NOT NULL PRIMARY KEY,
            title VARCHAR,
            channel_title VARCHAR,
            channel_id VARCHAR,
            published_at VARCHAR,
            category_id VARCHAR,
            view_count BIGINT,
            like_count BIGINT,
            comment_count BIGINT,
            duration_formatted BIGINT,
            made_for_kids BOOLEAN,
            tags VARCHAR,
            description VARCHAR,
            script VARCHAR,
            script_timestamp VARCHAR,
            collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 3. Comments 테이블 생성
        CREATE TABLE IF NOT EXISTS comments (
            comment_id VARCHAR NOT NULL PRIMARY KEY,
            video_id VARCHAR,
            author VARCHAR,
            author_channel_id VARCHAR,
            comment_text VARCHAR,
            like_count BIGINT,
            published_at VARCHAR,
            updated_at VARCHAR,
            reply_count BIGINT,
            is_reply BOOLEAN,
            parent_id VARCHAR,
            collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # 인덱스 생성 SQL
        create_indexes_sql = """
        -- 인덱스 생성 (성능 최적화)
        CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id);
        CREATE INDEX IF NOT EXISTS idx_comments_video_id ON comments(video_id);
        CREATE INDEX IF NOT EXISTS idx_comments_parent_id ON comments(parent_id);
        CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at);
        CREATE INDEX IF NOT EXISTS idx_comments_published_at ON comments(published_at);
        """
        
        try:
            # 데이터베이스 연결
            connection = psycopg2.connect(**self.db_config)
            cursor = connection.cursor()
            
            print("PostgreSQL 연결 성공!")
            
            # 테이블 생성
            cursor.execute(create_tables_sql)
            print("테이블 생성 완료!")
            
            # 인덱스 생성
            cursor.execute(create_indexes_sql)
            print("인덱스 생성 완료!")
            
            # 변경사항 커밋
            connection.commit()
            
            # 테이블 확인
            self.check_tables(cursor)
            
        except psycopg2.Error as e:
            print(f"데이터베이스 에러: {e}")
        except Exception as e:
            print(f"일반 에러: {e}")
        finally:
            # 연결 종료
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            print("데이터베이스 연결 종료")
    
    def check_tables(self, cursor):
        """생성된 테이블 확인"""
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print("\n생성된 테이블:")
        for table in tables:
            print(f"- {table[0]}")
    
    def get_connection(self):
        """데이터베이스 연결 반환 (다른 모듈에서 사용)"""
        try:
            return psycopg2.connect(**self.db_config)
        except psycopg2.Error as e:
            print(f"연결 실패: {e}")
            return None

    def save_channel_data(self, channel_data):
        """채널 데이터 저장"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 단일 채널 데이터인 경우 리스트로 변환
            if isinstance(channel_data, dict):
                channel_data = [channel_data]
            
            # INSERT SQL (ON CONFLICT로 중복 처리)
            insert_sql = """
                INSERT INTO channel (
                    channel_id, customUrl, title, country, description, 
                    published_at, etag, hiddenSubscriberCount, subscriberCount, 
                    videoCount, viewCount, thumbnail_url
                ) VALUES %s
                ON CONFLICT (channel_id) 
                DO UPDATE SET
                    customUrl = EXCLUDED.customUrl,
                    title = EXCLUDED.title,
                    country = EXCLUDED.country,
                    description = EXCLUDED.description,
                    published_at = EXCLUDED.published_at,
                    etag = EXCLUDED.etag,
                    hiddenSubscriberCount = EXCLUDED.hiddenSubscriberCount,
                    subscriberCount = EXCLUDED.subscriberCount,
                    videoCount = EXCLUDED.videoCount,
                    viewCount = EXCLUDED.viewCount,
                    thumbnail_url = EXCLUDED.thumbnail_url,
                    collection_time = CURRENT_TIMESTAMP;
            """
            
            # 데이터 준비
            values = []
            for channel in channel_data:
                values.append((
                    channel.get('channel_id'),
                    channel.get('customUrl'),
                    channel.get('title'),
                    channel.get('country'),
                    channel.get('description'),
                    channel.get('published_at'),
                    channel.get('etag'),
                    channel.get('hiddenSubscriberCount'),
                    channel.get('subscriberCount'),
                    channel.get('videoCount'),
                    channel.get('viewCount'),
                    channel.get('thumbnail_url')
                ))
            
            # 데이터 삽입
            execute_values(cursor, insert_sql, values)
            connection.commit()
            
            print(f"✅ 채널 데이터 {len(values)}개 저장 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 채널 데이터 저장 실패: {e}")
            connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                
    def save_video_data(self, video_data):
        """영상 데이터 저장"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 단일 영상 데이터인 경우 리스트로 변환
            if isinstance(video_data, dict):
                video_data = [video_data]
            
            # INSERT SQL
            insert_sql = """
                INSERT INTO videos (
                    video_id, title, channel_title, channel_id, published_at,
                    category_id, view_count, like_count, comment_count,
                    duration_formatted, made_for_kids, tags, description,
                    script, script_timestamp
                ) VALUES %s
                ON CONFLICT (video_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    channel_title = EXCLUDED.channel_title,
                    channel_id = EXCLUDED.channel_id,
                    published_at = EXCLUDED.published_at,
                    category_id = EXCLUDED.category_id,
                    view_count = EXCLUDED.view_count,
                    like_count = EXCLUDED.like_count,
                    comment_count = EXCLUDED.comment_count,
                    duration_formatted = EXCLUDED.duration_formatted,
                    made_for_kids = EXCLUDED.made_for_kids,
                    tags = EXCLUDED.tags,
                    description = EXCLUDED.description,
                    script = EXCLUDED.script,
                    script_timestamp = EXCLUDED.script_timestamp,
                    collection_time = CURRENT_TIMESTAMP;
            """
            
            # 데이터 준비
            values = []
            for video in video_data:
                # tags가 리스트인 경우 문자열로 변환
                tags = video.get('tags')
                if isinstance(tags, list):
                    tags = ', '.join(tags)
                
                values.append((
                    video.get('video_id'),
                    video.get('title'),
                    video.get('channel_title'),
                    video.get('channel_id'),
                    video.get('published_at'),
                    video.get('category_id'),
                    video.get('view_count'),
                    video.get('like_count'),
                    video.get('comment_count'),
                    video.get('duration_formatted'),
                    video.get('made_for_kids'),
                    tags,
                    video.get('description'),
                    video.get('script'),
                    video.get('script_timestamp')
                ))
            
            # 데이터 삽입
            execute_values(cursor, insert_sql, values)
            connection.commit()
            
            print(f"✅ 영상 데이터 {len(values)}개 저장 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 영상 데이터 저장 실패: {e}")
            connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                
    def save_comment_data(self, comment_data):
        """댓글 데이터 저장"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 단일 댓글 데이터인 경우 리스트로 변환
            if isinstance(comment_data, dict):
                comment_data = [comment_data]
            
            # INSERT SQL
            insert_sql = """
                INSERT INTO comments (
                    comment_id, video_id, author, author_channel_id, 
                    comment_text, like_count, published_at, updated_at,
                    reply_count, is_reply, parent_id
                ) VALUES %s
                ON CONFLICT (comment_id)
                DO UPDATE SET
                    video_id = EXCLUDED.video_id,
                    author = EXCLUDED.author,
                    author_channel_id = EXCLUDED.author_channel_id,
                    comment_text = EXCLUDED.comment_text,
                    like_count = EXCLUDED.like_count,
                    published_at = EXCLUDED.published_at,
                    updated_at = EXCLUDED.updated_at,
                    reply_count = EXCLUDED.reply_count,
                    is_reply = EXCLUDED.is_reply,
                    parent_id = EXCLUDED.parent_id,
                    collection_time = CURRENT_TIMESTAMP;
            """
            
            # 데이터 준비
            values = []
            for comment in comment_data:
                values.append((
                    comment.get('comment_id'),
                    comment.get('video_id'),
                    comment.get('author'),
                    comment.get('author_channel_id'),
                    comment.get('comment_text'),
                    comment.get('like_count'),
                    comment.get('published_at'),
                    comment.get('updated_at'),
                    comment.get('reply_count'),
                    comment.get('is_reply'),
                    comment.get('parent_id')
                ))
            
            # 데이터 삽입
            execute_values(cursor, insert_sql, values)
            connection.commit()
            
            print(f"✅ 댓글 데이터 {len(values)}개 저장 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 댓글 데이터 저장 실패: {e}")
            connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                
    def get_data_count(self):
        """저장된 데이터 개수 확인"""
        connection = self.get_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM channel;")
            channel_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos;")
            video_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM comments;")
            comment_count = cursor.fetchone()[0]
            
            print(f"📊 저장된 데이터:")
            print(f"   채널: {channel_count:,}개")
            print(f"   영상: {video_count:,}개")
            print(f"   댓글: {comment_count:,}개")
            
            return {
                'channels': channel_count,
                'videos': video_count,
                'comments': comment_count
            }
            
        except Exception as e:
            print(f"❌ 데이터 개수 조회 실패: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

                
    def get_connection(self):
        """데이터베이스 연결 반환"""
        try:
            return psycopg2.connect(**self.db_config)
        except psycopg2.Error as e:
            print(f"DB 연결 실패: {e}")
            return None
        
    import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv
from datetime import datetime
import json

class YouTubeDataSaver:
    def __init__(self):
        load_dotenv()
        
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'youtube_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD'),
            'port': int(os.getenv('DB_PORT', '5432'))
        }
    
    def get_connection(self):
        """데이터베이스 연결 반환"""
        try:
            return psycopg2.connect(**self.db_config)
        except psycopg2.Error as e:
            print(f"DB 연결 실패: {e}")
            return None
    
    def save_channel_data(self, channel_data):
        """채널 데이터 저장"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 단일 채널 데이터인 경우 리스트로 변환
            if isinstance(channel_data, dict):
                channel_data = [channel_data]
            
            # INSERT SQL (ON CONFLICT로 중복 처리)
            insert_sql = """
                INSERT INTO channel (
                    channel_id, customUrl, title, country, description, 
                    published_at, etag, hiddenSubscriberCount, subscriberCount, 
                    videoCount, viewCount, thumbnail_url
                ) VALUES %s
                ON CONFLICT (channel_id) 
                DO UPDATE SET
                    customUrl = EXCLUDED.customUrl,
                    title = EXCLUDED.title,
                    country = EXCLUDED.country,
                    description = EXCLUDED.description,
                    published_at = EXCLUDED.published_at,
                    etag = EXCLUDED.etag,
                    hiddenSubscriberCount = EXCLUDED.hiddenSubscriberCount,
                    subscriberCount = EXCLUDED.subscriberCount,
                    videoCount = EXCLUDED.videoCount,
                    viewCount = EXCLUDED.viewCount,
                    thumbnail_url = EXCLUDED.thumbnail_url,
                    collection_time = CURRENT_TIMESTAMP;
            """
            
            # 데이터 준비
            values = []
            for channel in channel_data:
                values.append((
                    channel.get('channel_id'),
                    channel.get('customUrl'),
                    channel.get('title'),
                    channel.get('country'),
                    channel.get('description'),
                    channel.get('published_at'),
                    channel.get('etag'),
                    channel.get('hiddenSubscriberCount'),
                    channel.get('subscriberCount'),
                    channel.get('videoCount'),
                    channel.get('viewCount'),
                    channel.get('thumbnail_url')
                ))
            
            # 데이터 삽입
            execute_values(cursor, insert_sql, values)
            connection.commit()
            
            print(f"✅ 채널 데이터 {len(values)}개 저장 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 채널 데이터 저장 실패: {e}")
            connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def save_video_data(self, video_data):
        """영상 데이터 저장"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 단일 영상 데이터인 경우 리스트로 변환
            if isinstance(video_data, dict):
                video_data = [video_data]
            
            # INSERT SQL
            insert_sql = """
                INSERT INTO videos (
                    video_id, title, channel_title, channel_id, published_at,
                    category_id, view_count, like_count, comment_count,
                    duration_formatted, made_for_kids, tags, description,
                    script, script_timestamp
                ) VALUES %s
                ON CONFLICT (video_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    channel_title = EXCLUDED.channel_title,
                    channel_id = EXCLUDED.channel_id,
                    published_at = EXCLUDED.published_at,
                    category_id = EXCLUDED.category_id,
                    view_count = EXCLUDED.view_count,
                    like_count = EXCLUDED.like_count,
                    comment_count = EXCLUDED.comment_count,
                    duration_formatted = EXCLUDED.duration_formatted,
                    made_for_kids = EXCLUDED.made_for_kids,
                    tags = EXCLUDED.tags,
                    description = EXCLUDED.description,
                    script = EXCLUDED.script,
                    script_timestamp = EXCLUDED.script_timestamp,
                    collection_time = CURRENT_TIMESTAMP;
            """
            
            # 데이터 준비
            values = []
            for video in video_data:
                # tags가 리스트인 경우 문자열로 변환
                tags = video.get('tags')
                if isinstance(tags, list):
                    tags = ', '.join(tags)
                
                values.append((
                    video.get('video_id'),
                    video.get('title'),
                    video.get('channel_title'),
                    video.get('channel_id'),
                    video.get('published_at'),
                    video.get('category_id'),
                    video.get('view_count'),
                    video.get('like_count'),
                    video.get('comment_count'),
                    video.get('duration_formatted'),
                    video.get('made_for_kids'),
                    tags,
                    video.get('description'),
                    video.get('script'),
                    video.get('script_timestamp')
                ))
            
            # 데이터 삽입
            execute_values(cursor, insert_sql, values)
            connection.commit()
            
            print(f"✅ 영상 데이터 {len(values)}개 저장 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 영상 데이터 저장 실패: {e}")
            connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def save_comment_data(self, comment_data):
        """댓글 데이터 저장"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # 단일 댓글 데이터인 경우 리스트로 변환
            if isinstance(comment_data, dict):
                comment_data = [comment_data]
            
            # INSERT SQL
            insert_sql = """
                INSERT INTO comments (
                    comment_id, video_id, author, author_channel_id, 
                    comment_text, like_count, published_at, updated_at,
                    reply_count, is_reply, parent_id
                ) VALUES %s
                ON CONFLICT (comment_id)
                DO UPDATE SET
                    video_id = EXCLUDED.video_id,
                    author = EXCLUDED.author,
                    author_channel_id = EXCLUDED.author_channel_id,
                    comment_text = EXCLUDED.comment_text,
                    like_count = EXCLUDED.like_count,
                    published_at = EXCLUDED.published_at,
                    updated_at = EXCLUDED.updated_at,
                    reply_count = EXCLUDED.reply_count,
                    is_reply = EXCLUDED.is_reply,
                    parent_id = EXCLUDED.parent_id,
                    collection_time = CURRENT_TIMESTAMP;
            """
            
            # 데이터 준비
            values = []
            for comment in comment_data:
                values.append((
                    comment.get('comment_id'),
                    comment.get('video_id'),
                    comment.get('author'),
                    comment.get('author_channel_id'),
                    comment.get('comment_text'),
                    comment.get('like_count'),
                    comment.get('published_at'),
                    comment.get('updated_at'),
                    comment.get('reply_count'),
                    comment.get('is_reply'),
                    comment.get('parent_id')
                ))
            
            # 데이터 삽입
            execute_values(cursor, insert_sql, values)
            connection.commit()
            
            print(f"✅ 댓글 데이터 {len(values)}개 저장 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 댓글 데이터 저장 실패: {e}")
            connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def get_data_count(self):
        """저장된 데이터 개수 확인"""
        connection = self.get_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM channel;")
            channel_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos;")
            video_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM comments;")
            comment_count = cursor.fetchone()[0]
            
            print(f"📊 저장된 데이터:")
            print(f"   채널: {channel_count:,}개")
            print(f"   영상: {video_count:,}개")
            print(f"   댓글: {comment_count:,}개")
            
            return {
                'channels': channel_count,
                'videos': video_count,
                'comments': comment_count
            }
            
        except Exception as e:
            print(f"❌ 데이터 개수 조회 실패: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def print_all_channels(self, limit=None):
        """모든 채널 데이터 출력"""
        connection = self.get_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            
            # LIMIT 적용
            sql = "SELECT * FROM channel ORDER BY collection_time DESC"
            if limit:
                sql += f" LIMIT {limit}"
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            if not rows:
                print("📭 저장된 채널 데이터가 없습니다.")
                return
            
            print(f"📺 채널 데이터 ({len(rows)}개):")
            print("=" * 100)
            
            for row in rows:
                print(f"채널 ID: {row[0]}")
                print(f"커스텀 URL: {row[1] or 'N/A'}")
                print(f"제목: {row[2] or 'N/A'}")
                print(f"국가: {row[3] or 'N/A'}")
                print(f"설명: {(row[4][:100] + '...') if row[4] and len(row[4]) > 100 else (row[4] or 'N/A')}")
                print(f"생성일: {row[5] or 'N/A'}")
                print(f"구독자수: {row[8]:,}명" if row[8] else "구독자수: N/A")
                print(f"영상수: {row[9]:,}개" if row[9] else "영상수: N/A")
                print(f"총조회수: {row[10]:,}회" if row[10] else "총조회수: N/A")
                print(f"수집시간: {row[12]}")
                print("-" * 50)
            
            return rows
            
        except Exception as e:
            print(f"❌ 채널 데이터 조회 실패: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

# 사용 예시
if __name__ == "__main__":
    
    # DB 셋업 인스턴스 생성
    db_setup = YouTubeDBSetup()
    
    # 테이블 생성
    db_setup.create_tables()
    
    print("YouTube 데이터베이스 셋업 완료!")