import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import logging
from datetime import datetime
import json

class DatabaseConnection:
    """데이터베이스 연결 관리 클래스"""
    
    def __init__(self):
        load_dotenv()
        
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'port': os.getenv('DB_PORT', '5432')
        }
        
        self.logger = logging.getLogger(__name__)
        self._validate_config()
        
    def _validate_config(self):
        """DB 설정 검증"""
        required_fields = ['database', 'user', 'password']
        missing = [field for field in required_fields if not self.db_config[field]]
        if missing:
            raise ValueError(f"DB 설정이 누락되었습니다: {missing}")
    
    def get_connection(self):
        """DB 연결 생성"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except psycopg2.Error as e:
            self.logger.error(f"DB 연결 실패: {e}")
            raise
    
    def get_connection_info(self):
        """
        현재 연결 정보 반환
        Returns:
            dict: 연결 정보
        """
        try:
            conn = self.get_connection()
            
            # 연결 정보 수집
            info = {
                'host': conn.get_dsn_parameters()['host'],
                'port': conn.get_dsn_parameters()['port'],
                'database': conn.get_dsn_parameters()['dbname'],
                'user': conn.get_dsn_parameters()['user'],
                'server_version': conn.server_version,
                'protocol_version': conn.protocol_version,
                'status': 'connected' if not conn.closed else 'closed',
                'encoding': conn.encoding
            }
            
            conn.close()
            return info
            
        except Exception as e:
            self.logger.error(f"연결 정보 조회 실패: {e}")
            return None

    def check_connection_status(self, conn):
        """
        기존 연결 객체의 상태 확인
        Args:
            conn: psycopg2 연결 객체
        Returns:
            dict: 연결 상태 정보
        """
        try:
            status_map = {
                0: 'TRANSACTION_STATUS_IDLE',
                1: 'TRANSACTION_STATUS_ACTIVE', 
                2: 'TRANSACTION_STATUS_INTRANS',
                3: 'TRANSACTION_STATUS_INERROR',
                4: 'TRANSACTION_STATUS_UNKNOWN'
            }
            
            return {
                'closed': conn.closed,
                'status': status_map.get(conn.get_transaction_status(), 'UNKNOWN'),
                'server_version': conn.server_version,
                'autocommit': conn.autocommit,
                'isolation_level': conn.isolation_level
            }
            
        except Exception as e:
            self.logger.error(f"연결 상태 확인 실패: {e}")
            return None

class DataUploader:
    """YouTube 데이터 업로드 전용 클래스"""
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db_conn = db_connection
        self.logger = logging.getLogger(__name__)
    
    def create_tables(self):
        """채널 데이터 테이블 생성"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS youtube_channels (
            id SERIAL PRIMARY KEY,
            channel_id VARCHAR(255) UNIQUE NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            published_at TIMESTAMP,
            thumbnail_url VARCHAR(500),
            country VARCHAR(100),
            view_count BIGINT DEFAULT 0,
            subscriber_count BIGINT DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            raw_data JSONB
        );
        
        CREATE INDEX IF NOT EXISTS idx_channel_id ON youtube_channels(channel_id);
        CREATE INDEX IF NOT EXISTS idx_subscriber_count ON youtube_channels(subscriber_count);
        CREATE INDEX IF NOT EXISTS idx_updated_at ON youtube_channels(updated_at);
        """
        
        with self.db_conn.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_table_sql)
                conn.commit()
                self.logger.info("테이블 생성 완료")
    
    def insert_channel(self, channel_data: Dict[str, Any]) -> bool:
        """단일 채널 데이터 삽입/업데이트"""
        insert_sql = """
        INSERT INTO youtube_channels (
            channel_id, title, description, published_at, thumbnail_url,
            country, view_count, subscriber_count, video_count, raw_data
        ) VALUES (
            %(channel_id)s, %(title)s, %(description)s, %(published_at)s, %(thumbnail_url)s,
            %(country)s, %(view_count)s, %(subscriber_count)s, %(video_count)s, %(raw_data)s
        )
        ON CONFLICT (channel_id) 
        DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            view_count = EXCLUDED.view_count,
            subscriber_count = EXCLUDED.subscriber_count,
            video_count = EXCLUDED.video_count,
            updated_at = CURRENT_TIMESTAMP,
            raw_data = EXCLUDED.raw_data
        RETURNING id
        """
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(insert_sql, channel_data)
                    result = cursor.fetchone()
                    conn.commit()
                    self.logger.info(f"채널 저장 완료: {channel_data['title']} (ID: {result[0]})")
                    return True
        except psycopg2.Error as e:
            self.logger.error(f"채널 저장 실패: {e}")
            return False
    
    def batch_insert_channels(self, channels_data: List[Dict[str, Any]]) -> int:
        """여러 채널 배치 삽입"""
        success_count = 0
        
        try:
            with self.db_conn.get_connection() as conn:
                insert_sql = """
                INSERT INTO youtube_channels (
                    channel_id, title, description, published_at, thumbnail_url,
                    country, view_count, subscriber_count, video_count, raw_data
                ) VALUES (
                    %(channel_id)s, %(title)s, %(description)s, %(published_at)s, %(thumbnail_url)s,
                    %(country)s, %(view_count)s, %(subscriber_count)s, %(video_count)s, %(raw_data)s
                )
                ON CONFLICT (channel_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    view_count = EXCLUDED.view_count,
                    subscriber_count = EXCLUDED.subscriber_count,
                    video_count = EXCLUDED.video_count,
                    updated_at = CURRENT_TIMESTAMP,
                    raw_data = EXCLUDED.raw_data
                """
                
                with conn.cursor() as cursor:
                    for channel_data in channels_data:
                        try:
                            cursor.execute(insert_sql, channel_data)
                            success_count += 1
                        except psycopg2.Error as e:
                            self.logger.warning(f"개별 채널 저장 실패: {e}")
                            continue
                    
                    conn.commit()
                    self.logger.info(f"배치 삽입 완료: {success_count}/{len(channels_data)}")
                    
        except psycopg2.Error as e:
            self.logger.error(f"배치 삽입 실패: {e}")
        
        return success_count
    
    def delete_channel(self, channel_id: str) -> bool:
        """채널 데이터 삭제"""
        delete_sql = "DELETE FROM youtube_channels WHERE channel_id = %s"
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(delete_sql, (channel_id,))
                    deleted_count = cursor.rowcount
                    conn.commit()
                    
                    if deleted_count > 0:
                        self.logger.info(f"채널 삭제 완료: {channel_id}")
                        return True
                    else:
                        self.logger.warning(f"삭제할 채널을 찾을 수 없음: {channel_id}")
                        return False
                        
        except psycopg2.Error as e:
            self.logger.error(f"채널 삭제 실패: {e}")
            return False

class DataReader:
    """데이터 조회 전용 클래스"""
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db_conn = db_connection
        self.logger = logging.getLogger(__name__)
    
    def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """채널 ID로 데이터 조회"""
        select_sql = "SELECT * FROM youtube_channels WHERE channel_id = %s"
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(select_sql, (channel_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except psycopg2.Error as e:
            self.logger.error(f"채널 조회 실패: {e}")
            return None
    
    def get_all_channels(self, limit: int = 100, offset: int = 0, order_by: str = 'subscriber_count') -> List[Dict[str, Any]]:
        """모든 채널 조회 (페이지네이션 지원)"""
        allowed_orders = ['subscriber_count', 'view_count', 'video_count', 'created_at', 'title']
        if order_by not in allowed_orders:
            order_by = 'subscriber_count'
        
        select_sql = f"""
        SELECT * FROM youtube_channels 
        ORDER BY {order_by} DESC 
        LIMIT %s OFFSET %s
        """
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(select_sql, (limit, offset))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except psycopg2.Error as e:
            self.logger.error(f"채널 목록 조회 실패: {e}")
            return []
    
    def search_channels(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """키워드로 채널 검색"""
        search_sql = """
        SELECT * FROM youtube_channels 
        WHERE title ILIKE %s OR description ILIKE %s
        ORDER BY subscriber_count DESC
        LIMIT %s
        """
        
        search_term = f"%{keyword}%"
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(search_sql, (search_term, search_term, limit))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except psycopg2.Error as e:
            self.logger.error(f"채널 검색 실패: {e}")
            return []
    
    def get_top_channels(self, metric: str = 'subscriber_count', limit: int = 10) -> List[Dict[str, Any]]:
        """상위 채널 조회"""
        allowed_metrics = ['subscriber_count', 'view_count', 'video_count']
        if metric not in allowed_metrics:
            metric = 'subscriber_count'
        
        select_sql = f"""
        SELECT * FROM youtube_channels 
        ORDER BY {metric} DESC 
        LIMIT %s
        """
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(select_sql, (limit,))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except psycopg2.Error as e:
            self.logger.error(f"상위 채널 조회 실패: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """데이터베이스 통계 조회"""
        stats_sql = """
        SELECT 
            COUNT(*) as total_channels,
            AVG(subscriber_count) as avg_subscribers,
            MAX(subscriber_count) as max_subscribers,
            MIN(subscriber_count) as min_subscribers,
            SUM(view_count) as total_views
        FROM youtube_channels
        """
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(stats_sql)
                    result = cursor.fetchone()
                    return dict(result) if result else {}
        except psycopg2.Error as e:
            self.logger.error(f"통계 조회 실패: {e}")
            return {}
    
    def get_channels_by_country(self, country: str, limit: int = 50) -> List[Dict[str, Any]]:
        """국가별 채널 조회"""
        select_sql = """
        SELECT * FROM youtube_channels 
        WHERE country = %s
        ORDER BY subscriber_count DESC
        LIMIT %s
        """
        
        try:
            with self.db_conn.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(select_sql, (country, limit))
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except psycopg2.Error as e:
            self.logger.error(f"국가별 채널 조회 실패: {e}")
            return []

class DataManager:
    """데이터 업로더와 리더를 관리하는 매니저 클래스"""
    
    def __init__(self):
        self.connection = DatabaseConnection()
        self.uploader = DataUploader(self.db_connection)
        self.reader = DataReader(self.db_connection)
        self.logger = logging.getLogger(__name__)
    
    
    def store_channel_data(self, channel_data: Dict[str, Any]) -> bool:
        """채널 데이터 저장 (고수준 메서드)"""
        # 원본 데이터를 JSON 문자열로 변환
        if 'raw_data' in channel_data and not isinstance(channel_data['raw_data'], str):
            channel_data['raw_data'] = json.dumps(channel_data['raw_data'])
        
        return self.uploader.insert_channel(channel_data)
    
    def store_multiple_channels(self, channels_data: List[Dict[str, Any]]) -> int:
        """여러 채널 데이터 저장"""
        # 모든 raw_data를 JSON 문자열로 변환
        for channel_data in channels_data:
            if 'raw_data' in channel_data and not isinstance(channel_data['raw_data'], str):
                channel_data['raw_data'] = json.dumps(channel_data['raw_data'])
        
        return self.uploader.batch_insert_channels(channels_data)
    
    def find_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """채널 찾기"""
        return self.reader.get_channel_by_id(channel_id)
    
    def list_channels(self, page: int = 1, page_size: int = 50, sort_by: str = 'subscriber_count') -> Dict[str, Any]:
        """채널 목록 조회 (페이지네이션)"""
        offset = (page - 1) * page_size
        channels = self.reader.get_all_channels(limit=page_size, offset=offset, order_by=sort_by)
        stats = self.reader.get_statistics()
        
        return {
            'channels': channels,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': stats.get('total_channels', 0)
            },
            'statistics': stats
        }
    
    def search_and_analyze(self, keyword: str) -> Dict[str, Any]:
        """검색 및 분석"""
        search_results = self.reader.search_channels(keyword)
        
        if not search_results:
            return {'results': [], 'analysis': {}}
        
        # 간단한 분석
        total_subscribers = sum(ch['subscriber_count'] for ch in search_results)
        avg_subscribers = total_subscribers / len(search_results)
        
        analysis = {
            'total_channels_found': len(search_results),
            'total_subscribers': total_subscribers,
            'average_subscribers': avg_subscribers,
            'top_channel': max(search_results, key=lambda x: x['subscriber_count'])['title']
        }
        
        return {
            'results': search_results,
            'analysis': analysis
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """대시보드용 데이터 조회"""
        stats = self.reader.get_statistics()
        top_by_subscribers = self.reader.get_top_channels('subscriber_count', 5)
        top_by_views = self.reader.get_top_channels('view_count', 5)
        
        return {
            'overview': stats,
            'top_subscribers': top_by_subscribers,
            'top_views': top_by_views
        }