import re
import logging
from ..interfaces import ISubtitleProcessor

class SubtitleProcessor(ISubtitleProcessor):
    """자막 처리기 구현"""
    
    def convert_format(self, input_path: str, output_path: str, target_format: str) -> bool:
        """자막 형식 변환"""
        try:
            if target_format.lower() == 'txt':
                return self._convert_to_text(input_path, output_path)
            else:
                raise ValueError(f"지원하지 않는 형식: {target_format}")
        except Exception as e:
            logging.error(f"형식 변환 오류: {e}")
            return False
    
    def _convert_to_text(self, input_path: str, output_path: str) -> bool:
        """SRT를 텍스트로 변환"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            text = self.extract_text(content)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            return True
        except Exception as e:
            logging.error(f"텍스트 변환 오류: {e}")
            return False
    
    def extract_text(self, content: str) -> str:
        """SRT 내용에서 텍스트만 추출"""
        if not content:
            return ""
        
        lines = content.split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # 번호나 타임스탬프가 아닌 실제 텍스트만 추출
            if line and not line.isdigit() and '-->' not in line:
                # HTML 태그 제거
                line = re.sub(r'<[^>]+>', '', line)
                text_lines.append(line)
        
        return ' '.join(text_lines)