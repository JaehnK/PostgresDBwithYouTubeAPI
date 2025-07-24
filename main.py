from pprint import pprint
from youtube_api_handler import YouTubeAPIHandler
from youtube_db_architecture import *

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
        output_dir="./example1_output",
        default_subtitle_languages=['ko']
    )
    workflow = srcs.YouTubeWorkflow(config)    
    video_url = "https://www.youtube.com/watch?v=QH1MQ9OajwY"
    result = workflow.process_single_video(video_url)
    pprint(result)
        
if __name__ == "__main__":
    channel_info = dict()
    channel_info['leebonggyuTv'] = 'UCxuf3GXK290vcpFW0lxm0Uw'
    
    main()
