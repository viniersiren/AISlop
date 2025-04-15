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
    "title": "🦇 What We Do in the Shadows | Short Clip | {timestamp}",
    "description": "Highlight from *What We Do in the Shadows* 🧛‍♂️\n#Shorts ENJOY, LIKE COMMENT",
    "tags": [
        "whatwedointheshadows", "wwdits", "movieshorts", "filmclips",
        "moviemoments", "editing", "vampirecomedy", "short", "shorts"
    ],
    "category": "24"  # Entertainment
}

VIDEO_METADATA = {
    "title": "🦇 What We Do in the Shadows |  | {timestamp}",
    "description": "Eedited compilation of hilarious moments from *What We Do in the Shadows* 🧛‍♀️\n\nCreated by our advanced video processing system.\n#WWDITS #Shorts",
    "tags": [
        "whatwedointheshadows", "wwdits", "movietime", "filmclips", "aigenerated",
        "moviecompilation", "automatedediting", "vampirehumor"
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


def upload_to_youtube(video_file, title, description, thumbnail_path=None):  # Made thumbnail optional
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
            "tags": ["AI", "movie clips", "automation"],
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

def upload_to_youtube_single(video_file, is_short=True):
    """Handle YouTube upload with metadata configuration"""
    metadata = SHORT_METADATA if is_short else VIDEO_METADATA
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    
    # Format metadata
    title = metadata["title"].format(timestamp=timestamp)
    description = metadata["description"]
    tags = metadata["tags"]
    
    #thumbnail = metadata["thumbnail"]
    category = metadata["category"]

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
        
        # Add thumbnail if available
        # if os.path.exists(thumbnail):
        #     try:
        #         time.sleep(10)  # Wait for YouTube processing
        #         youtube.thumbnails().set(
        #             videoId=response["id"],
        #             media_body=MediaFileUpload(thumbnail, mimetype='image/jpeg')
        #         ).execute()
        #         print("Thumbnail uploaded successfully")
        #     except Exception as e:
        #         print(f"Thumbnail error: {str(e)}")
        # else:
        #     print(f"No thumbnail found at {thumbnail}")
        
        return response['id']
    
    except Exception as e:
        print(f"Upload failed: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Upload video to YouTube')
    parser.add_argument('video_path', type=str, help='Path to video file')
    parser.add_argument('upload_type', type=int, choices=[1, 2], 
                      help='1 for regular video, 2 for Short')
    args = parser.parse_args()

    # Process video if it's a short
    if args.upload_type == 2:
        print("Processing as Short...")
        processed_path = os.path.splitext(args.video_path)[0] + "_vertical.mp4"
        final_video = ensure_vertical_video(args.video_path, processed_path)
    else:
        print("Processing as regular video...")
        final_video = args.video_path

    # Upload with appropriate metadata
    upload_to_youtube_single(final_video, is_short=(args.upload_type == 2))

if __name__ == "__main__":
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    main()