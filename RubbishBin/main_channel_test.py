from pprint import pprint

import srcs

def main():
    config = srcs.YouTubeConfig(
        output_dir="./captions",
        default_subtitle_languages=['ko']
    )
    
    factory = srcs.YouTubeServiceFactory(config)
    database = factory.create_db_connector()
    database.create_tables()
    workflow = srcs.YouTubeWorkflow(config)
    
    
    video_url = "https://www.youtube.com/watch?v=ZAsBykWi0bc8"
    
    # result = workflow.process_single_video(video_url, {
    # 'include_comments': True,      # 댓글 포함
    # 'save_comments_to_file': True,
    # 'include_raw_comments' : True
    # })
    workflow.process_channel_information('@haruplaylist-123')

        
if __name__ == "__main__":    
    main()
