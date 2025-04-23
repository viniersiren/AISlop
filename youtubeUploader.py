import os
import json
import random
import argparse
import subprocess
import time
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Static configuration
SHORT_METADATA = {
    "title": " Insider Trading in *What We Do in the Shadows* | Vampire Finance Short 📈🧛",

    "description": """Welcome to *What We Do in the Shadows* – where vampires dabble in... insider trading?

- Nandor learns about Wall Street (sort of)
- Laszlo thinks “insider” means something *very* different
- Colin Robinson gives a thrilling lecture on SEC regulations

📉 Vampires and the stock market? What could go wrong.

#WWDITS #WhatWeDoInTheShadows #ComedyShorts #VampireHumor #InsiderTrading #FinanceParody #Mockumentary #Shorts #SitcomFinance
""",

    "tags": [
        "whatwedointheshadows", "wwdits", "shorts", "vampirecomedy",
        "sitcomfinance", "insidertrading", "mockumentary", "tvparody", "funnyclips"
    ],
    "category": "24"  # Entertainment
}


VIDEO_METADATA = {
    "title": "📈 Insider Trading Gets Undead in *What We Do in the Shadows* | Vampire Finance – Part 21 | {timestamp}",

    "description": """*What We Do in the Shadows* tackles... financial crimes?

Nandor and Laszlo try to get rich quick with “insider trading,” but their vampire logic might not hold up in court. Colin Robinson, of course, thrives.

AI-edited for maximum mockumentary madness and financial chaos.

#WWDITS #WhatWeDoInTheShadows #VampireFinance #ComedyShorts #MockumentaryMadness #InsiderTradingParody #SitcomHumor #TVClips #AIClips
""",

    "tags": [
        "whatwedointheshadows", "wwdits", "insidertrading", "vampiresitcom",
        "financecomedy", "mockumentary", "tvhumor", "sitcomclips", "aivideo"
    ],
    "category": "24"
}






def ensure_vertical_video(input_path, output_path, target_aspect_ratio=9/16):
    """Convert video to vertical 9:16 format with a top bar of 15% and a bottom bar of 25% of the target height."""
    clip = VideoFileClip(input_path)
    width, height = clip.size
    current_aspect_ratio = width / height

    if current_aspect_ratio <= target_aspect_ratio:
        print("Video is already vertical.")
        clip.close()
        return input_path

    print("Converting to vertical aspect ratio (9:16)...")

    # Set final vertical resolution (e.g., 1080x1920)
    target_height = 1920
    target_width = int(target_height * target_aspect_ratio)  # 1080 for 9:16

    # Define top and bottom black bars heights
    top_bar_height = int(target_height * 0.15)
    bottom_bar_height = int(target_height * 0.25)
    
    # Calculate the visible area height for the original video (remaining 60%)
    visible_height = target_height - top_bar_height - bottom_bar_height

    # Resize original clip to fit visible height
    resized_clip = clip.resized(height=visible_height)

    # Center horizontally; position vertically by top bar height
    x_center = (target_width - resized_clip.w) // 2
    y_offset = top_bar_height

    video_with_position = resized_clip.with_position((x_center, y_offset))

    # Create a black background that includes the bars and visible area
    background = ColorClip(size=(target_width, target_height), color=(0, 0, 0), duration=clip.duration)

    # Composite the final video
    final = CompositeVideoClip([background, video_with_position])
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast")

    clip.close()
    return output_path


def upload_to_youtube(video_file, title, description, tags, thumbnail_path=None):  # Made thumbnail optional
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "24",
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    try:
        media_body = MediaFileUpload(video_file, mimetype='video/mp4', resumable=True)
        response = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media_body
        ).execute()
        
        print(f"Successfully uploaded video ID: {response['id']}")
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                # Add delay to allow video processing
                time.sleep(10)
                youtube.thumbnails().set(
                    videoId=response["id"],
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
                ).execute()
                print("Thumbnail uploaded successfully")
            except Exception as thumbnail_error:
                print(f"Thumbnail upload failed: {str(thumbnail_error)}")
        
        return response['id']
    
    except Exception as upload_error:
        print(f"Upload failed: {str(upload_error)}")
        return None

def upload_to_youtube_single(video_file, metadata_file, is_short=True):
    """Handle YouTube upload with metadata configuration"""

    with open(metadata_file, 'r') as mf:
        metadata = json.load(mf)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    title = metadata['title'].format(timestamp=timestamp)
    description = metadata['description']
    tags = metadata.get('tags', [])
    category = metadata.get('category', '24')

    # Authentication flow
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    # Build request body
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category,
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    try:
        # Upload video
        media_body = MediaFileUpload(video_file, mimetype='video/mp4', resumable=True)
        response = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media_body
        ).execute()
        
        print(f"Uploaded video ID: {response['id']}")
        
        
        return response['id']
    
    except Exception as e:
        print(f"Upload failed: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Upload video to YouTube')
    parser.add_argument('video_path', help='Path to video file')
    parser.add_argument('metadata_file', help='Path to JSON metadata file')
    parser.add_argument('upload_type', type=int, choices=[1,2],
                        help='1: full video, 2: YouTube Short')
    args = parser.parse_args()

    if args.upload_type == 2:
        print('Processing a short')
        processed = os.path.splitext(args.video_path)[0] + '_vertical.mp4'
        final_video = ensure_vertical_video(args.video_path, processed)
    else:
        final_video = args.video_path

    upload_to_youtube_single(final_video, args.metadata_file)

if __name__ == "__main__":
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    main()