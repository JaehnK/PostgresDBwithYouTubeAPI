from abc import ABC, abstractmethod
from typing import Dict, List, Any

class IYouTubeDao(ABC):
    """DB 접근자 클래스"""
    
    @abstractmethod
    def create_tables(self):
        """테이블 생성 프로시저"""
        pass
    
    @abstractmethod
    def save_channel_data(self, channel_data):
        """채널 데이터 저장"""
        pass
    
    @abstractmethod
    def save_video_data(self, video_data):
        """영상 데이터 저장"""
        pass
        
    @abstractmethod
    def save_comment_data(self, comment_data):
        """댓글 저장"""
        pass