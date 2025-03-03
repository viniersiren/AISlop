import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# YouTube API configuration
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/cloud-platform"]

# Function to upload to YouTube
def upload_to_youtube(video_file, title, description, thumbnail_path):
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
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
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    # Upload video
    media_body = open(video_file, "rb")
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_body
    )

    response = request.execute()
    print("Uploaded to YouTube:", response["id"])

    # Upload thumbnail
    youtube.thumbnails().set(
        videoId=response["id"],
        media_body=thumbnail_path
    ).execute()

    print(f"Thumbnail uploaded for video ID: {response['id']}")

# MAIN SCRIPT
if __name__ == "__main__":
    video_file = "clips/clip_processed.mp4"
    title = "Sample Video Title"
    description = "This is an example description for the video"
    thumbnail_path = "clips/thumbnail.jpg"

    upload_to_youtube(video_file, title, description, thumbnail_path)
