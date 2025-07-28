from pprint import pprint
from srcs.YouTubeServiceFactory import YouTubeServiceFactory

import srcs

def main():
    
    # crawling_handler = YouTubeAPIHandler()
    

    # # pprint(crawling_handler.get_channel_info(channel_info['leebonggyuTv']))
    # pprint(crawling_handler.get_channel_info('@MrBeast'))
    # # pprint(crawling_handler.get_all_videos('@sogunom')

    # # db = DataManager()
    # # conn = db.connection.get_connection()
    # # pprint(db.connection.get_connection_info())
    
    config = srcs.YouTubeConfig(
        output_dir="./captions",
        default_subtitle_languages=['ko']
    )
    
    factory = YouTubeServiceFactory(config)
    database = factory.create_db_connector()
    database.create_tables()
    workflow = srcs.YouTubeWorkflow(config)
    
    
    video_url = "https://www.youtube.com/watch?v=cWtngWBBDXM"
    
    result = workflow.process_single_video(video_url, {
    'include_comments': True,      # 댓글 포함
    'save_comments_to_file': True,
    'include_raw_comments' : True
    })
    
    channel_ids = database.get_unique_channel_ids()
    for i in channel_ids:
        workflow.process_channel_information(i)
# 메타데이터 + 자막 + 댓글 모두 처리
    #pprint(result)
        
if __name__ == "__main__":
    channel_info = dict()
    channel_info['leebonggyuTv'] = 'UCxuf3GXK290vcpFW0lxm0Uw'
    
    main()
