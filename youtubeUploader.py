import os
import json
import argparse
import subprocess
import time
import gc
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import datetime
from datetime import datetime, timezone


# Default scopes for YouTube uploads and channel management
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

CLIENT_SECRETS_DEFAULT = "client_secrets.json"


def load_credentials(token_path, scopes):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if creds:
        # show token expiry
        if creds.expiry:
            expiry = creds.expiry
            # ensure expiry is timezone-aware UTC
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = expiry - now
            print(f"Token expires at {expiry.isoformat()} (in {delta.total_seconds()/3600:.1f} hours)")

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
        # re-show expiry after refresh
        if creds.expiry:
            expiry = creds.expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = expiry - now
            print(f"[refreshed] Token now expires at {expiry.isoformat()} (in {delta.total_seconds()/3600:.1f} hours)")

    return creds


def authorize(token_path, scopes, client_secrets):
    print('authorizing')
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, scopes)
    creds = flow.run_local_server(
        port=9129,
        access_type="offline",
        prompt="consent"
    )
    with open(token_path, "w") as token_file:
        token_file.write(creds.to_json())
    print(f"Saved new credentials to {token_path}")
    return creds


def get_authenticated_service(token_path, scopes, client_secrets):
    creds = load_credentials(token_path, scopes)
    if not creds or not creds.valid:
        creds = authorize(token_path, scopes, client_secrets)
    return build("youtube", "v3", credentials=creds)


def ensure_vertical_video(input_path, output_path, target_aspect_ratio=9/16):
    """Convert video to vertical 9:16 format with top and bottom bars."""
    clip = VideoFileClip(input_path)
    if os.path.exists(output_path):
        print(f"Vertical video already exists at {output_path}, skipping conversion.")
        return output_path
    width, height = clip.size
    current_aspect_ratio = width / height

    if current_aspect_ratio <= target_aspect_ratio:
        print("Video is already vertical.")
        clip.close()
        return input_path

    print("Converting to vertical aspect ratio (9:16)...")
    target_height = 1920
    target_width = int(target_height * target_aspect_ratio)
    top_bar_height = int(target_height * 0.15)
    bottom_bar_height = int(target_height * 0.25)
    visible_height = target_height - top_bar_height - bottom_bar_height
    resized_clip = clip.resized(height=visible_height)
    x_center = (target_width - resized_clip.w) // 2
    y_offset = top_bar_height
    video_with_position = resized_clip.with_position((x_center, y_offset))
    background = ColorClip(size=(target_width, target_height), color=(0, 0, 0), duration=clip.duration)
    final = CompositeVideoClip([background, video_with_position])
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast")
    clip.close()

    cleanup_clip(final)   # close the CompositeVideoClip you just wrote
    cleanup_clip(clip)

    return output_path


def upload_to_youtube(
    video_file,
    title,
    description,
    tags,
    thumbnail_path=None,
    channel=None,
    token_path=None,
    scopes=None,
    client_secrets=None
):
    # Determine token file
    if token_path is None and channel:
        token_path = f"token_{channel}.json"
    scopes = scopes or DEFAULT_SCOPES
    client_secrets = client_secrets or CLIENT_SECRETS_DEFAULT

    # Build (or rebuild) the YouTube client for this channel
    youtube = get_authenticated_service(token_path, scopes, client_secrets)

    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags + '#YouTubeShorts, #viral, #trending, #foryou, #fyp, #explorepage, #discover, #viralvideo, #reels, #subscribe, #shorts',
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
            time.sleep(10)
            try:
                youtube.thumbnails().set(
                    videoId=response["id"],
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
                ).execute()
                print("Thumbnail uploaded successfully")
            except Exception as thumbnail_error:
                print(f"Thumbnail upload failed: {thumbnail_error}")

        return response['id']

    except Exception as upload_error:
        print(f"Upload failed: {upload_error}")
        return None



def upload_to_youtube_single(video_file, metadata_file, youtube):
    with open(metadata_file, 'r') as mf:
        metadata = json.load(mf)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    title = metadata['title'].format(timestamp=timestamp)
    description = metadata['description']
    tags = metadata.get('tags', [])
    category = metadata.get('category', '24')

    # Override category if provided in metadata
    youtube._baseUrl = youtube._baseUrl.replace('/v3/', '/v3/')  # placeholder to retain build
    return upload_to_youtube(video_file, title, description, tags, metadata.get('thumbnail'), youtube)


def cleanup_clip(clip):
    """
    Gracefully closes all readers on a MoviePy clip (video & audio),
    deletes the reference, and forces garbage collection.
    """
    try:
        clip.close()
        if hasattr(clip, "reader"):
            clip.reader.close()
        if hasattr(clip, "audio") and hasattr(clip.audio, "reader"):
            clip.audio.reader.close_proc()
    except Exception as e:
        print(f"Warning during clip cleanup: {e}")
    finally:
        # remove reference and collect
        del clip
        gc.collect()

def main():
    parser = argparse.ArgumentParser(description='Upload video(s) to YouTube, with multi-channel support')
    parser.add_argument('video_path', help='Path to video file')
    parser.add_argument('metadata_file', help='Path to JSON metadata file')
    parser.add_argument('upload_type', type=int, choices=[1,2],
                        help='1: full video, 2: YouTube Short')
    parser.add_argument('--channel', default='default',
                        help='Name of the YouTube channel (used to select token file)')
    parser.add_argument('--token-file', default=None,
                        help='Explicit path to token JSON; overrides channel-based naming')
    parser.add_argument('--client-secrets', default=CLIENT_SECRETS_DEFAULT,
                        help='Path to OAuth client secrets JSON')
    parser.add_argument('--scopes', nargs='+', default=DEFAULT_SCOPES,
                        help='OAuth scopes to request')
    args = parser.parse_args()

    token_path = args.token_file or f"token_{args.channel}.json"
    print(f"Using token file: {token_path}")

    # Determine video to upload
    if args.upload_type == 2:
        print('Processing a short')
        processed = os.path.splitext(args.video_path)[0] + '_vertical.mp4'
        final_video = ensure_vertical_video(args.video_path, processed)
    else:
        final_video = args.video_path

    # Build YouTube service with chosen credentials
    youtube = get_authenticated_service(token_path, args.scopes, args.client_secrets)

    # Upload and exit
    upload_to_youtube_single(final_video, args.metadata_file, youtube)

if __name__ == "__main__":
    main()
