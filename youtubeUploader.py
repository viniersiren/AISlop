import os
import json
import random
import subprocess
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip

def ensure_vertical_video(input_path, output_path, target_aspect_ratio=9/16):
    clip = VideoFileClip(input_path)
    width, height = clip.size
    current_aspect_ratio = width / height

    if current_aspect_ratio <= target_aspect_ratio:
        print("Video is already vertical.")
        clip.close()
        return input_path  # Already vertical

    print("Converting to vertical aspect ratio (9:16)...")
    target_height = height
    target_width = int(target_height * target_aspect_ratio)

    resized_clip = clip.resized(height=target_height)
    x_centered_clip = resized_clip.with_position(("center", "center"))

    background = ColorClip(size=(target_width, target_height), color=(0, 0, 0), duration=clip.duration)
    final = CompositeVideoClip([background, x_centered_clip])
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast")

    clip.close()
    return output_path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/cloud-platform"]
import time  # Add this at the top of the file with other imports

def upload_to_youtube(video_file, title, description, thumbnail_path=None):  # Made thumbnail optional
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