import requests
from typing import List, Dict, Optional

class CompleteCommentCollector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3/commentThreads"
        self.comments_url = "https://www.googleapis.com/youtube/v3/comments"  # 대댓글용 엔드포인트
    
    def extract_comment_data(self, item: Dict, video_id: str, is_reply: bool = False, parent_id: str = '') -> Dict:
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
            'like_count': snippet['likeCount'],
            'published_at': snippet['publishedAt'],
            'updated_at': snippet['updatedAt'],
            'reply_count': item['snippet'].get('totalReplyCount', 0) if not is_reply else 0,
            'is_reply': is_reply,
            'parent_id': parent_id,
            'reply_depth': 1 if is_reply and parent_id else 0  # 답글 깊이 추가
        }
    
    def get_all_replies(self, parent_id: str, video_id: str) -> List[Dict]:
        """특정 댓글의 모든 답글 수집 (대댓글 포함)"""
        all_replies = []
        next_page_token = None
        
        while True:
            params = {
                'part': 'snippet',
                'parentId': parent_id,
                'maxResults': 100,
                'key': self.api_key
            }
            
            if next_page_token:
                params['pageToken'] = next_page_token
            
            try:
                response = requests.get(self.comments_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for item in data.get('items', []):
                        reply_data = self.extract_comment_data(item, video_id, is_reply=True, parent_id=parent_id)
                        all_replies.append(reply_data)
                    
                    next_page_token = data.get('nextPageToken')
                    if not next_page_token:
                        break
                        
                elif response.status_code == 404:
                    # 답글이 없거나 삭제됨
                    print(f"  ⚠️ 댓글 {parent_id}의 답글을 찾을 수 없습니다.")
                    break
                else:
                    print(f"  ❌ 답글 수집 실패: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"  ❌ 답글 수집 중 오류: {e}")
                break
        
        return all_replies
    
    def collect_complete_comments(self, video_id: str) -> List[Dict]:
        """모든 댓글과 대댓글을 완전히 수집"""
        print(f"\n📹 비디오 ID: {video_id} 완전한 댓글 수집 시작")
        
        all_comments = []
        next_page_token = None
        page_count = 0
        
        while True:
            # 최상위 댓글 수집
            params = {
                'part': 'snippet,replies',
                'videoId': video_id,
                'maxResults': 100,
                'order': 'time',
                'key': self.api_key
            }
            
            if next_page_token:
                params['pageToken'] = next_page_token
            
            try:
                response = requests.get(self.base_url, params=params)
                
                if response.status_code != 200:
                    print(f"❌ API 요청 실패: {response.status_code}")
                    break
                
                data = response.json()
                page_count += 1
                page_comments = 0
                
                for item in data.get('items', []):
                    # 1. 최상위 댓글 추가
                    top_comment = self.extract_comment_data(item, video_id)
                    all_comments.append(top_comment)
                    page_comments += 1
                    
                    # 2. API 응답에 포함된 답글들 (일부만)
                    api_replies = []
                    if 'replies' in item:
                        for reply in item['replies']['comments']:
                            reply_data = self.extract_comment_data(reply, video_id, is_reply=True, parent_id=item['id'])
                            api_replies.append(reply_data)
                            all_comments.append(reply_data)
                            page_comments += 1
                    
                    # 3. 답글이 더 있는 경우 모든 답글 수집
                    total_reply_count = item['snippet']['totalReplyCount']
                    if total_reply_count > len(api_replies):
                        print(f"  🔍 댓글 {item['id']}: {total_reply_count}개 답글 중 {len(api_replies)}개만 로드됨, 나머지 수집 중...")
                        
                        # 모든 답글 별도 수집
                        complete_replies = self.get_all_replies(item['id'], video_id)
                        
                        # API 응답에 이미 포함된 답글 제외
                        api_reply_ids = {reply['comment_id'] for reply in api_replies}
                        new_replies = [reply for reply in complete_replies if reply['comment_id'] not in api_reply_ids]
                        
                        all_comments.extend(new_replies)
                        page_comments += len(new_replies)
                        
                        print(f"  ✅ 추가 답글 {len(new_replies)}개 수집 완료")
                
                print(f"  📄 {page_count}페이지: {page_comments}개 댓글 (총 {len(all_comments):,}개)")
                
                # 다음 페이지 확인
                next_page_token = data.get('nextPageToken')
                if not next_page_token:
                    print(f"  ✅ 모든 댓글 및 대댓글 수집 완료!")
                    break
                    
            except Exception as e:
                print(f"❌ 수집 중 오류: {e}")
                break
        
        print(f"📊 비디오 {video_id}: 총 {len(all_comments):,}개 댓글 수집 완료")
        return all_comments
    
    def analyze_comment_structure(self, comments: List[Dict]) -> Dict:
        """댓글 구조 분석"""
        analysis = {
            'total_comments': len(comments),
            'top_level_comments': 0,
            'replies': 0,
            'threads_with_replies': 0,
            'max_replies_per_thread': 0,
            'total_threads': 0
        }
        
        # 최상위 댓글들과 답글들 분리
        top_level = [c for c in comments if not c['is_reply']]
        replies = [c for c in comments if c['is_reply']]
        
        analysis['top_level_comments'] = len(top_level)
        analysis['replies'] = len(replies)
        analysis['total_threads'] = len(top_level)
        
        # 답글이 있는 스레드 수 계산
        threads_with_replies = set()
        reply_counts = {}
        
        for reply in replies:
            parent_id = reply['parent_id']
            threads_with_replies.add(parent_id)
            reply_counts[parent_id] = reply_counts.get(parent_id, 0) + 1
        
        analysis['threads_with_replies'] = len(threads_with_replies)
        analysis['max_replies_per_thread'] = max(reply_counts.values()) if reply_counts else 0
        
        return analysis

# 사용 예제
def main():
    import os
    import dotenv
    dotenv.load_dotenv()
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    video_id = "mV89q23WSjE"
    
    collector = CompleteCommentCollector(API_KEY)
    
    # 완전한 댓글 수집
    all_comments = collector.collect_complete_comments(video_id)
    
    # 구조 분석
    analysis = collector.analyze_comment_structure(all_comments)
    
    print("\n" + "="*50)
    print("📊 댓글 구조 분석")
    print("="*50)
    print(f"총 댓글 수: {analysis['total_comments']:,}개")
    print(f"최상위 댓글: {analysis['top_level_comments']:,}개")
    print(f"답글: {analysis['replies']:,}개")
    print(f"답글이 있는 스레드: {analysis['threads_with_replies']:,}개")
    print(f"스레드당 최대 답글 수: {analysis['max_replies_per_thread']:,}개")
    print("="*50)
    
    # CSV로 저장
    import pandas as pd
    df = pd.DataFrame(all_comments)
    df.to_csv(f"complete_comments_{video_id}.csv", index=False, encoding='utf-8-sig')
    print(f"💾 완전한 댓글 데이터가 저장되었습니다.")

if __name__ == "__main__":
    main()