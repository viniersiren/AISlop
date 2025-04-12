import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import random
import subprocess

# YouTube API configuration
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/cloud-platform"]


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
    media_body = MediaFileUpload(video_file, mimetype='video/mp4', resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_body
    )

    response = request.execute()

    youtube.thumbnails().set(
        videoId=response["id"],
        media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
    ).execute()


    print(f"Thumbnail uploaded for video ID: {response['id']}")

# MAIN SCRIPT
if __name__ == "__main__":
    video_file = "clips/clip_80_processed.mp4"

    video = MediaFileUpload(
        filename=video_file,  # make sure this is a string
        mimetype=video_file,
        resumable=True
    )
    # Generate a thumbnail at a random timestamp
    duration_cmd = ['ffprobe', '-v', 'error', '-show_entries',
                    'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_file]
    duration = float(subprocess.check_output(duration_cmd).decode().strip())
    random_time = round(random.uniform(1, max(duration - 2, 1)), 2)

    thumbnail_path = "clips/thumbnail.jpg"
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(random_time), "-i", video_file,
        "-vframes", "1", "-q:v", "2", thumbnail_path
    ])

    # Fun, searchable YouTube metadata
    title = "Lady Vampire Wrecks the Office Party 🧛‍♀️ | What We Do in the Shadows"
    description = (
        "Things get out of hand when a vampire crashes the office party — with Laszlo, an off-brand Frankenstein, "
        "and a whole lot of broken furniture. Classic 'What We Do in the Shadows' chaos. 🩸🧟‍♂️\n\n"
        "#WhatWeDoInTheShadows #VampireComedy #Laszlo #FrankensteinVibes #OfficePartyFromHell #FX #WWDITS #Shorts"
    )

    upload_to_youtube(video_file, title, description, thumbnail_path)
