from abc import ABC, abstractmethod

class ISubtitleProcessor(ABC):
    """자막 처리기 인터페이스"""
    
    @abstractmethod
    def convert_format(self, input_path: str, output_path: str, target_format: str) -> bool:
        pass
    
    @abstractmethod
    def extract_text(self, content: str) -> str:
        pass