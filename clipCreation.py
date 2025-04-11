
import os
import json
import random
import wave
import subprocess
#from moviepy.editor import *
from vosk import Model, KaldiRecognizer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# CONFIGURATION
MOVIE_FILE = "output.mp4"  # Change this to your movie/show file
MIN_CLIP_LENGTH = 10  # Minimum clip length in seconds
MAX_CLIP_LENGTH = 40  # Maximum clip length in seconds
CURSE_WORDS = ["fuck", "shit", "damn", "bitch", "ass", "hell"]
BLEEP_FILE = "bleep.mp3"  # Add bleep sound file
CURSE_PROBABILITY = 0.05  # 5% chance
ZOOM_FACTOR = 1.2  # How much to zoom (1.2 = 20% zoom)
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
    # Generate a random clip length between MIN_CLIP_LENGTH and MAX_CLIP_LENGTH
    clip_length = random.randint(MIN_CLIP_LENGTH, MAX_CLIP_LENGTH)

    # Convert start_time (in seconds) to HH:MM:SS format
    hours = start_time // 3600
    minutes = (start_time % 3600) // 60
    seconds = start_time % 60
    start_time_formatted = f"{hours:02}:{minutes:02}:{seconds:02}"

    # Convert clip_length to HH:MM:SS format
    clip_hours = clip_length // 3600
    clip_minutes = (clip_length % 3600) // 60
    clip_seconds = clip_length % 60
    clip_length_formatted = f"{clip_hours:02}:{clip_minutes:02}:{clip_seconds:02}"

    try:
        # Construct the ffmpeg command with quoted paths and formatted clip length
        cmd = f'ffmpeg -i "{movie_file}" -ss {start_time_formatted} -to {clip_length_formatted} -c:v libx264 -c:a aac -y "{output_file}"'

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
            words = result["text"].split()
            for word in words:
                if random.random() < CURSE_PROBABILITY:  # 5% chance of inserting a curse word
                    captions += "[BLEEP] "
                else:
                    captions += word + " "
    return captions.strip()

def create_fast_cuts(video_file):
    print("Creating fast cuts...")
    clip = VideoFileClip(video_file)
    subclips = []
    new_clip_length = clip.duration

    # Increase the number of cuts and make them more random
    min_cuts = 5
    max_cuts = 10
    num_cuts = random.randint(min_cuts, max_cuts)

    # Generate random start and end times for each subclip
    for _ in range(num_cuts):
        start = random.uniform(0, new_clip_length - 0.5)  # Ensure at least 0.5 seconds for each clip
        end = start + random.uniform(0.5, 1.5)  # Subclips between 0.5 and 1.5 seconds

        if end > new_clip_length:
            end = new_clip_length

        subclip = clip.subclip(start, end)

        # Apply zoom effect randomly with more variations
        if random.random() > 0.3:  # 70% chance of applying zoom
            zoom_factor = random.uniform(1.1, 1.5)  # Zoom between 10% and 50%
            if random.random() > 0.5:
                zoom_factor = 1 / zoom_factor  # Zoom out

            subclip = subclip.fx(
                vfx.resize, zoom_factor
            ).fx(
                vfx.crop,
                x_center=subclip.w / 2,
                y_center=subclip.h / 2,
                width=subclip.w / zoom_factor,
                height=subclip.h / zoom_factor,
            )

        subclips.append(subclip)

    # Apply crossfade transitions
    final_clip = concatenate_videoclips(subclips, method="compose", padding=-TRANSITION_DURATION)
    return final_clip

# Function to add captions to video
def add_captions(video, captions):
    txt_clip = TextClip(captions, fontsize=24, color='white', size=(video.w * 0.8, None), method='caption')
    txt_clip = txt_clip.set_position(("center", "bottom")).set_duration(video.duration)
    return CompositeVideoClip([video, txt_clip])

def add_music(video, music_file):
    music = AudioFileClip(music_file).volumex(MUSIC_VOLUME).set_duration(video.duration)

    audio_clip = video.audio

    if audio_clip is None:
        audio_clip = music
    return video.set_audio(audio_clip)

def add_bleeps(video, captions, bleep_file=BLEEP_FILE):
    """Adds bleep sounds to the video where [BLEEP] is found in captions."""
    bleep_sound = AudioFileClip(bleep_file)
    bleep_duration = bleep_sound.duration
    audio = video.audio
    
    # Find bleep locations based on the captions
    bleep_locations = [i for i, word in enumerate(captions.split()) if word == "[BLEEP]"]
    
    # Create a list of audio clips to be composited
    audio_clips = [audio]
    
    # Add the bleep sound effects
    for location in bleep_locations:
        start_time = 0
        
        for i, word in enumerate(captions.split()):
            
            if i == location :
                
                
                bleep_clip = bleep_sound.set_start(start_time)
                audio_clips.append(bleep_clip)
            try:
                start_time += len(word) / 5 #approx word time in secs
            except:
                start_time += bleep_duration
                
    final_audio = CompositeAudioClip(audio_clips)
    
    # Set the final audio to the video clip
    return video.set_audio(final_audio)

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
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": "public",
        },
    }

    media_body = open(video_file, "rb")
    request = youtube.videos().insert(
        part="snippet,status", body=request_body, media_body=media_body
    )
    response = request.execute()
    print("Uploaded to YouTube:", response["id"])


# MAIN SCRIPT
def get_unique_filename(base_filename):
    # Start with the base filename and check if it exists
    i = 0
    while os.path.exists(base_filename):
        # Increment i and check again until a unique filename is found
        i += 1
        base_filename = f"{base_filename.rsplit('.', 1)[0]}_{i}.mp4"  # Append the index before the extension
    return base_filename


if __name__ == "__main__":
    # Generate only one clip
    start_time = random.randint(0, 3600)  # Random time within the first hour

    # Check if clip_0.mp4 exists, then clip_1.mp4, and so on until we find a unique filename
    i = 0
    while True:
        clip_file = os.path.join(OUTPUT_FOLDER, f"clip_{i}.mp4")
        if not os.path.exists(clip_file):  # If the file doesn't exist, break out of the loop
            break
        i += 1

    processed_file = os.path.join(OUTPUT_FOLDER, f"clip_{i}_processed.mp4")
    while os.path.exists(processed_file):  # Ensure processed file also has a unique name
        i += 1
        processed_file = os.path.join(OUTPUT_FOLDER, f"clip_{i}_processed.mp4")

    print(f"Extracting clip {i+1}...")
    extract_clip(MOVIE_FILE, start_time, clip_file)


    print("did it save????")
    captions = transcribe_audio(clip_file)

    print("Applying AI editing...")
    fast_cut_clip = create_fast_cuts(clip_file)
    captioned_clip = add_captions(fast_cut_clip, captions)

    print("adding bleep sounds...")
    final_clip = add_bleeps(captioned_clip,captions)

    print("before muzax")
    final_clip = add_music(final_clip, MUSIC_FILE)
    print("Saving final video...")
    final_clip.write_videofile(processed_file, codec="libx264", fps=24)

    print("Uploading to YouTube...")
    #upload_to_youtube(processed_file, f"AI-Generated Clip {i+1}", "Automatically generated movie/show clip")

    print("Clip processed and uploaded!")