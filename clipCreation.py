
import os
import json
import random
import wave
import subprocess
from moviepy import (
    VideoFileClip, 
    TextClip, 
    CompositeVideoClip, 
    concatenate_videoclips, 
    vfx, 
    afx,
    AudioFileClip,
    CompositeAudioClip,
    ColorClip
)

from vosk import Model, KaldiRecognizer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import tempfile


# CONFIGURATION
MOVIE_FILE = "output.mp4"  # Change this to your movie/show file
MIN_CLIP_LENGTH = 45  # Minimum clip length in seconds
MAX_CLIP_LENGTH = 80  # Maximum clip length in seconds
CURSE_WORDS = ["fuck", "shit", "damn", "bitch", "ass", "hell"]
BLEEP_FILE = "bleep.mp3"  # Add bleep sound file
CURSE_PROBABILITY = 0.05  # 5% chance
ZOOM_FACTOR = 1.2  # How much to zoom (1.2 = 20% zoom)
TRANSITION_DURATION = 0.5  # Seconds of smooth transition between cuts
MUSIC_FILE = "timeless galaxy.mp3"  # Background music (royalty-free)
MUSIC_VOLUME = 0.2  # Adjust background music volume (0.0 - 1.0)
VOSK_MODEL_PATH = "models/vosk-model-en-us-0.22"
OUTPUT_FOLDER = "clips/"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Function to extract a random clip
def extract_clip(movie_file, start_time, output_file):
    # First get video duration
    probe_cmd = [
        'ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of',
        'default=noprint_wrappers=1:nokey=1', movie_file
    ]
    
    try:
        duration = float(subprocess.check_output(probe_cmd))
    except Exception as e:
        print(f"Error getting duration: {str(e)}")
        return

    # Generate valid clip parameters
    max_possible_start = duration - MIN_CLIP_LENGTH
    if max_possible_start < 0:
        raise ValueError("Source video is too short")
        
    start_time = random.uniform(0, max_possible_start)
    #clip_length = random.randint(MIN_CLIP_LENGTH, min(MAX_CLIP_LENGTH, duration - start_time))
    clip_length = 7

    # Use proper FFmpeg command with duration (-t) instead of end time (-to)
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', movie_file,
        '-t', str(clip_length),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-map_chapters', '-1',  # Remove chapters
        '-map_metadata', '-1',  # Remove metadata
        output_file
    ]
    
    try:
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        print(f"Clip extracted: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg failed: {e.stderr.decode()}")

# Function to transcribe using Vosk
def transcribe_audio(video_file):
    print("TRANSCRIBING")

    # Check for audio
    probe_cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'a',
        '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', video_file
    ]
    
    try:
        has_audio = subprocess.check_output(probe_cmd).decode().strip() == 'audio'
    except subprocess.CalledProcessError:
        has_audio = False

    if not has_audio:
        print("Warning: No audio track found in video")
        return "[No speech detected]", []

    # Extract audio to temporary WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        convert_cmd = [
            'ffmpeg', '-y', '-i', video_file,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            temp_audio.name
        ]
        
        try:
            subprocess.run(convert_cmd, check=True, 
                          stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"Audio conversion failed: {e.stderr.decode()}")
            return "[Audio extraction failed]", []

    # Transcribe from temporary WAV file
    model = Model(VOSK_MODEL_PATH)
    wf = wave.open(temp_audio.name, 'rb')
    os.unlink(temp_audio.name)
    
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    captions = []
    timings = []

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if 'result' in result:
                for word_info in result['result']:
                    word = word_info['word']
                    start = word_info['start']
                    end = word_info['end']

                    if random.random() < CURSE_PROBABILITY:
                        captions.append("shit")
                    else:
                        captions.append(word)
                    timings.append((start, end))

    # Process final result
    final_result = json.loads(rec.FinalResult())
    if 'result' in final_result:
        for word_info in final_result['result']:
            word = word_info['word']
            start = word_info['start']
            end = word_info['end']

            if random.random() < CURSE_PROBABILITY:
                captions.append("[SHIT]")
            else:
                captions.append(word)
            timings.append((start, end))

    return " ".join(captions), timings

def create_fast_cuts(video_file):
    print("Creating fast cuts...")
    clip = VideoFileClip(video_file)
    subclips = []
    new_clip_length = clip.duration

    # Increase the number of cuts and make them more random
    min_cuts = 5
    max_cuts = 10
    num_cuts = random.randint(min_cuts, max_cuts)

    for _ in range(num_cuts):
        start = random.uniform(0, new_clip_length - 0.5)
        end = start + random.uniform(0.5, 1.5)
        end = min(end, new_clip_length)

        # Get subclip using legacy syntax
        subclip = clip.subclipped(start, end)

        if random.random() > 0.3:
            zoom_factor = random.uniform(1.1, 1.5)
            if random.random() > 0.5:
                zoom_factor = 1 / zoom_factor

            # Legacy-compatible resize and crop
            original_w, original_h = subclip.size
            new_w = int(original_w * zoom_factor)
            new_h = int(original_h * zoom_factor)
            
            # Resize first
            resized = subclip.resized((new_w, new_h))
            
            # Then crop using direct vfx call
            # cropped = vfx.Crop(
            #     resized,
            #     x1=(new_w - original_w)//2,
            #     y1=(new_h - original_h)//2,
            #     x2=(new_w + original_w)//2,
            #     y2=(new_h + original_h)//2
            # )
            
            # subclip = cropped

        subclips.append(subclip)

    # Use legacy concatenation method
    final_clip = concatenate_videoclips(subclips, 
                                      padding=-TRANSITION_DURATION)
    return final_clip

def add_captions(video, captions, timings):
    # Debug: Print input parameters
    print(f"Adding captions to video. Captions count: {len(captions.split())}, Timings count: {len(timings)}")
    
    if isinstance(video, str):
        print(f"Loading video from file: {video}")
        video = VideoFileClip(video)
    
    width, height = video.size
    print(f"Video dimensions: {width}x{height}, Duration: {video.duration}s")

    clips = [video]
    
    # Create caption background
    caption_bg = ColorClip(
        size=(width, 100),
        color=(0, 0, 0),
        duration=video.duration
    ).with_opacity(0.7).with_position(("center", height-100))
    #clips.append(caption_bg)
    print("Created caption background")

    words = captions.split()
    
    # Debug: Verify alignment
    if len(words) != len(timings):
        print(f"ERROR: Mismatched captions ({len(words)}) and timings ({len(timings)})")
        return video  # Fallback to original video

    for i, (word, (start, end)) in enumerate(zip(words, timings)):
        try:
            # Debug: Print current word info
            print(f"Processing word {i+1}/{len(words)}: '{word}' ({start:.2f}-{end:.2f}s)")
            
            if word == "[BLEEP]":  # Changed from [SHIT] to match transcription
                # Create censor bar
                txt = TextClip(
                    text="▓"*random.randint(3, 6),
                    font="./premadeTest/shortfarm/fonts/font.ttf",
                    font_size=60,
                    color='red',
                    stroke_color='black',
                    stroke_width=1
                )
                print(f"Created censor bar for bleep at {start:.2f}s")
            else:
                # Create normal text
                txt = TextClip(
                    text=word,
                    font="./premadeTest/shortfarm/fonts/font.ttf",
                    font_size=60,
                    color='white',
                    stroke_color='black',
                    stroke_width=1
                )
                txt.save_frame("debug_frame.png") 
                print(f"Created text clip for '{word}'")

            # Calculate position with slight randomness
            y_pos = height  + random.randint(-5, 5)
            print(f"Positioning at y={y_pos}")

            # Set clip properties
            txt = txt.with_start(start)\
                    .with_end(end)\
                    .with_position(("center", y_pos))\
                    #.crossfadein(0.1)\
                    #.crossfadeout(0.1)
            
            clips.append(txt)
        
        except Exception as e:
            print(f"Error processing word '{word}': {str(e)}")
            continue

    print(f"Created {len(clips)-2} text clips")  # Subtract video and background
    
    try:
        final_clip = CompositeVideoClip(clips)  # Use ALL clips
        print("Successfully composed video with captions")
        return final_clip
    except Exception as e:
        print(f"Error composing video: {str(e)}")
        return video

def add_music(video, music_file):
    # Load music and adjust volume
    music = AudioFileClip(music_file)
    
    music.with_effects([afx.MultiplyVolume(0.001)])
    
    # Set music duration to match video
    music = music.with_duration(video.duration)
    
    # Mix audio tracks
    if video.audio:
        combined_audio = CompositeAudioClip([video.audio, music])
    else:
        combined_audio = music
        
    return video.with_audio(combined_audio)


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
                
                
                bleep_clip = bleep_sound.with_start(start_time)
                audio_clips.append(bleep_clip)
            try:
                start_time += len(word) / 5 #approx word time in secs
            except:
                start_time += bleep_duration
                
    final_audio = CompositeAudioClip(audio_clips)
    
    # Set the final audio to the video clip
    return video.with_audio(final_audio)

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
    start_time = random.randint(0, 1200)  # Random time within the first hour

   
    #create_fast_cuts("clips/clip_26.mp4")
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

    #clip_file = os.path.join(OUTPUT_FOLDER, "clip_54.mp4")
    print("did it save????")
    captions, timings = transcribe_audio(clip_file)
    
    # transcription_file = os.path.join(OUTPUT_FOLDER, "clip_54_transcription.json")
    # with open(transcription_file, 'r') as f:
    #     transcription_data = json.load(f)
    # captions = transcription_data['captions']
    # timings = transcription_data['timings']

    # clip_file = os.path.join(OUTPUT_FOLDER, "clip_54.mp4")
    print("adding caption...")
    #fast_cut_clip = create_fast_cuts(clip_file)
    captioned_clip = add_captions(clip_file, captions, timings)

    print("adding bleep sounds...")
    final_clip = add_bleeps(captioned_clip,captions)

    print("before muzax")
    final_clip = add_music(final_clip, MUSIC_FILE)
    print("Saving final video...")
    final_clip.write_videofile(processed_file, codec="libx264")

    print("Uploading to YouTube...")
    #upload_to_youtube(processed_file, f"AI-Generated Clip {i+1}", "Automatically generated movie/show clip")

    print("Clip processed and uploaded!")



    #music = AudioFileClip(music_file)
    #music.with_effects([afx.MultiplyVolume(0.5)])