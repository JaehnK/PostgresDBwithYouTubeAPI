from pprint import pprint
from youtube_api_handler import YouTubeAPIHandler
from youtube_db_architecture import *

def main():
    
    crawling_handler = YouTubeAPIHandler()
    

    # pprint(crawling_handler.get_channel_info(channel_info['leebonggyuTv']))
    pprint(crawling_handler.get_channel_info('@sogunom'))
    # pprint(crawling_handler.get_all_videos('@sogunom'))


    db = DataManager()
    conn = db.connection.get_connection()
    pprint(db.connection.get_connection_info())
    
    
if __name__ == "__main__":
    channel_info = dict()
    channel_info['leebonggyuTv'] = 'UCxuf3GXK290vcpFW0lxm0Uw'
    
    main()
