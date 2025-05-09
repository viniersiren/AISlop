import os
import json
import pickle
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Constants
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
CREDENTIALS_FILE = 'client_secrets.json'
TOKEN_FILE = 'token.pickle'
CHANNEL_ID = 'YOUR_CHANNEL_ID'  # Replace with your channel ID

def get_authenticated_service():
    """Get authenticated YouTube service with refreshable tokens."""
    credentials = None
    
    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
    
    # Refresh token if expired
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    
    # If no valid credentials, get new ones
    if not credentials or not credentials.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(f"Please place your {CREDENTIALS_FILE} in the script directory")
        
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        
        # Save the credentials
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    
    return build('youtube', 'v3', credentials=credentials)

def upload_video(video_path, title, description, tags, category_id='22'):  # 22 is for People & Blogs
    """Upload a video to YouTube."""
    try:
        youtube = get_authenticated_service()
        
        # Prepare the video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': 'private',  # Start as private for review
                'selfDeclaredMadeForKids': False
            }
        }
        
        # Create the upload request
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True
        )
        
        # Execute the upload
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        print(f"Uploading video: {title}")
        response = request.execute()
        
        # Get the video ID
        video_id = response['id']
        video_url = f"https://youtu.be/{video_id}"
        
        print(f"Upload complete! Video URL: {video_url}")
        return video_id, video_url
        
    except Exception as e:
        print(f"Error uploading video: {str(e)}")
        return None, None

def update_video_privacy(video_id, privacy_status='public'):
    """Update the privacy status of an uploaded video."""
    try:
        youtube = get_authenticated_service()
        
        request = youtube.videos().update(
            part='status',
            body={
                'id': video_id,
                'status': {
                    'privacyStatus': privacy_status
                }
            }
        )
        
        response = request.execute()
        print(f"Video privacy updated to {privacy_status}")
        return True
        
    except Exception as e:
        print(f"Error updating video privacy: {str(e)}")
        return False

def main():
    # Example usage
    video_path = "generated_videos/lore_short_20240315_123456.mp4"
    title = "The Elder Scrolls Lore: Skyrim"
    description = "Explore the rich lore of The Elder Scrolls universe."
    tags = ["elder scrolls", "lore", "skyrim", "gaming", "tes"]
    
    video_id, video_url = upload_video(video_path, title, description, tags)
    if video_id:
        # Update to public after review
        update_video_privacy(video_id, 'public')

if __name__ == "__main__":
    main() 