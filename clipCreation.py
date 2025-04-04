import os
import json
import random
import wave
import subprocess
from moviepy import (
    VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, vfx, AudioFileClip
)
from vosk import Model, KaldiRecognizer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

#
# CONFIGURATION
MOVIE_FILE = "output.mp4"  # Change this to your movie/show file
CLIP_LENGTH = "00:00:30"  # Length of the full extracted clip in seconds
ZOOM_FACTOR = 1.2  # How much to zoom (1.2 = 20% zoom)
CUTS_PER_CLIP = 3  # Number of fast cuts per clip
TRANSITION_DURATION = 0.5  # Seconds of smooth transition between cuts
MUSIC_FILE = "royalty_free_music.mp3"  # Background music (royalty-free)
MUSIC_VOLUME = 0.2  # Adjust background music volume (0.0 - 1.0)
VOSK_MODEL_PATH = "models/vosk-model-en-us-0.22"
OUTPUT_FOLDER = "clips/"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to extract a random clip
def extract_clip(movie_file, start_time, output_file):
    # Convert start_time (in seconds) to HH:MM:SS format
    hours = start_time // 3600
    minutes = (start_time % 3600) // 60
    seconds = start_time % 60
    start_time_formatted = f"{hours:02}:{minutes:02}:{seconds:02}"

    try:
        # Construct the ffmpeg command with quoted paths
        cmd = f'ffmpeg -i "{movie_file}" -ss {start_time_formatted} -t {CLIP_LENGTH} -c:v libx264 -c:a aac -y "{output_file}"'
        
        # Run the command and capture any errors
        subprocess.run(cmd, shell=True, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        print(f"Clip extracted successfully to {output_file}")
    
    except subprocess.CalledProcessError as e:
        print(f"Error extracting clip: {e.stderr.decode()}")
    except ValueError as ve:
        print(f"Invalid time format: {ve}")
    except Exception as e:
        print(f"Unexpected error: {e}")

# Function to transcribe using Vosk
def transcribe_audio(audio_file):
    model = Model(VOSK_MODEL_PATH)
    wf = wave.open(audio_file, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    captions = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            captions += result["text"] + " "
    
    return captions.strip()

def create_fast_cuts(video_file):
    print("0")
    clip = VideoFileClip(video_file, fps_source='fps')

    print("1")
    subclips = []
    new_clip_length = clip.duration  # Get actual duration of the extracted clip
    segment_length = new_clip_length / CUTS_PER_CLIP  # Use float division
    for i in range(CUTS_PER_CLIP):
        start = i * segment_length
        end = start + segment_length
        subclip = clip.subclipped(start, end)
        
        # Apply zoom effect randomly
        if random.random() > 0.5:
            subclip = subclip.with_effects([
                vfx.Resize(ZOOM_FACTOR),
                vfx.Crop(
                    x_center=subclip.w / 2,
                    y_center=subclip.h / 2,
                    width=subclip.w / ZOOM_FACTOR,
                    height=subclip.h / ZOOM_FACTOR
                )
            ])
        
        subclips.append(subclip)

    # Apply crossfade transitions
    print("2")
    final_clip = concatenate_videoclips(subclips, method="compose", padding=-TRANSITION_DURATION)
    return final_clip

# Function to add captions to video
def add_captions(video, captions):
    txt_clip = TextClip(captions, fontsize=24, color='white', size=(video.w * 0.8, None), method='caption')
    txt_clip = txt_clip.set_position(("center", "bottom")).set_duration(video.duration)
    return CompositeVideoClip([video, txt_clip])

# Function to add background music
def add_music(video, music_file):
    music = AudioFileClip(music_file).volumex(MUSIC_VOLUME).set_duration(video.duration)
    return video.set_audio(music)

# Function to upload to YouTube
def upload_to_youtube(video_file, title, description):
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
            "categoryId": "24"  # Entertainment
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media_body = open(video_file, "rb")
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_body
    )
    response = request.execute()
    print("Uploaded to YouTube:", response["id"])

def generate_unique_filename(folder, prefix, extension):
    i = 0
    while True:
        filename = os.path.join(folder, f"{prefix}_{i}.{extension}")
        if not os.path.exists(filename):
            return filename
        i += 1

if __name__ == "__main__":
    start_time = random.randint(0, 3600)
    clip_file = generate_unique_filename(OUTPUT_FOLDER, "clip", "mp4")

    print(f"Extracting clip...")
    extract_clip(MOVIE_FILE, start_time, clip_file)
      
    print("Generating captions...")
    # captions = transcribe_audio(clip_file)

    print("Applying AI editing...")
    fast_cut_clip = create_fast_cuts(clip_file)
    # captioned_clip = add_captions(fast_cut_clip, captions)
    # final_clip = add_music(fast_cut_clip, MUSIC_FILE)

    print("Saving final video...")
    fast_cut_clip.write_videofile(clip_file, codec="libx264", fps=24)

    print("Uploading to YouTube...")
    upload_to_youtube(clip_file, "AI-Generated Clip", "Automatically generated movie/show clip")

    print("Clip processed and uploaded!")