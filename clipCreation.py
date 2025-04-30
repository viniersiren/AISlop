import os
import json
import random
import wave
import subprocess
import numpy as np
import sys
import gc
import re
import time
import argparse

from fastCuts import create_fast_cuts
from transcribeAndCaption import add_captions, transcribe_audio
from geminiTitleGen import generate_youtube_metadata

from moviepy import (
    VideoFileClip, 
    TextClip, 
    CompositeVideoClip, 
    concatenate_videoclips, 
    vfx, 
    afx,
    AudioFileClip,
    CompositeAudioClip,
    ColorClip,
    
)

from vosk import Model, KaldiRecognizer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import tempfile


# CONFIGURATION
#Fury(2014).mp4
#vietVet1.mp4
MOVIE_FILE = "./TwiceAgainInput/thenightmarkets4e4.mp4"  # Change this to your movie/show file
MIN_CLIP_LENGTH = 25  # Minimum clip length in seconds
MAX_CLIP_LENGTH = 65  # Maximum clip length in seconds
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


MASS_MODE = False
if '3' in sys.argv:
    sys.argv.remove('3')
    MASS_MODE = True

parser = argparse.ArgumentParser()
parser.add_argument("--input", dest="movie_file", help="Path to source video")
parser.add_argument("--output", dest="output_folder", help="Directory to save clips")
args = parser.parse_args()

if args.movie_file:
    MOVIE_FILE = args.movie_file
if args.output_folder:
    OUTPUT_FOLDER = args.output_folder

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# CONFIGURATION
MOVIE_FILE = MOVIE_FILE  # e.g. "./TwiceAgainInput/thenightmarkets4e4.mp4"
MIN_CLIP_LENGTH = 25

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# Function to extract a random clip
def extract_clip(movie_file, output_file, start_time=None):  # Modified to accept optional start_time
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
        
    # If start_time is not provided, generate random
    if start_time is None:
        start_time = random.uniform(0, max_possible_start)
    else:  # Clamp to valid range
        start_time = max(0, min(start_time, max_possible_start))
    
    clip_length = random.randint(MIN_CLIP_LENGTH, min(MAX_CLIP_LENGTH, duration - start_time))
    #clip_length = 30

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



def get_random_music_file():
    music_folder = "./music"
    music_files = [f for f in os.listdir(music_folder) if f.endswith(".mp3")]
    if not music_files:
        raise Exception("No .mp3 files found in the music folder.")
    return os.path.join(music_folder, random.choice(music_files))

def add_music(video, music_file):
    # Load music and adjust volume
    music = AudioFileClip(music_file)
    
    music = music.with_effects([afx.MultiplyVolume(0.02)])
    
    # Set music duration to match video
    music = music.with_duration(video.duration)

    videoAud1 = video.audio.with_effects([afx.MultiplyVolume(1.2)])
    
    # Mix audio tracks
    if video.audio:
        combined_audio = CompositeAudioClip([videoAud1, music])
    else:
        combined_audio = music
        
    return video.with_audio(combined_audio)


def add_bleeps(video, captions, bleep_file=BLEEP_FILE):
    """Adds bleep sounds to the video where [BLEEP] is found in captions."""
    bleep_sound = AudioFileClip(bleep_file)
    bleep_sound = AudioFileClip(bleep_file).subclipped(0, 0.25)
    bleep_duration = bleep_sound.duration
    audio = video.audio
    
    # Find bleep locations based on the captions
    bleep_locations = [i for i, word in enumerate(captions.split()) if word in CURSE_WORDS or word == "[BLEEP]"]
    
    # Create a list of audio clips to be composited
    audio_clips = [audio]
    
    # Add the bleep sound effects
    for location in bleep_locations:
        start_time = 0
        
       # for i, word in enumerate(captions.split()):
        #    print('')
            # if i == location :
            #     bleep_clip = bleep_sound.with_start(start_time)
            #     audio_clips.append(bleep_clip)
            # try:
            #     start_time += len(word) / 5 #approx word time in secs
            # except:
            #     start_time += bleep_duration
                
    final_audio = CompositeAudioClip(audio_clips)
    
    # Set the final audio to the video clip
    return video.with_audio(final_audio)

# MAIN SCRIPT
def get_unique_filename(base_filename):
    # Start with the base filename and check if it exists
    i = 0
    while os.path.exists(base_filename):
        # Increment i and check again until a unique filename is found
        i += 1
        base_filename = f"{base_filename.rsplit('.', 1)[0]}_{i}.mp4"  # Append the index before the extension
    return base_filename


def try_generate_metadata(captions, movie_file, max_retries=5):
    for attempt in range(max_retries):
        try:
            short_metadata = generate_youtube_metadata(captions, movie_file[:-4], metadata_dir=OUTPUT_FOLDER)
            if short_metadata:  # check for valid output (adjust as needed)
                return short_metadata
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        time.sleep(1)  # optional delay between retries
    raise RuntimeError("Failed to generate metadata after multiple attempts.")

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

if __name__ == "__main__":
    if MASS_MODE: #len(sys.argv) > 1 and sys.argv[1] == '3':
        # Mass production mode
        #mass_folder = os.path.join(OUTPUT_FOLDER, "./TwiceAgainInput/thenightmarket")
        print('called mass production')
        input_basename = os.path.splitext(os.path.basename(MOVIE_FILE))[0]
        mass_folder = os.path.join(OUTPUT_FOLDER, input_basename)
        os.makedirs(mass_folder, exist_ok=True)
        print('MASS PRODUCING')
        # Get source duration
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', MOVIE_FILE
        ]
        duration = float(subprocess.check_output(probe_cmd))
        end_time = duration - 120  # Last 2 minutes
        
        existing_clips = [f for f in os.listdir(mass_folder) if re.fullmatch(r"\d+\.mp4", f)]
        existing_indices = sorted([int(re.match(r"(\d+)", f).group()) for f in existing_clips])
        if existing_indices:
            clip_idx = existing_indices[-1] + 1
            start_time = sum(VideoFileClip(os.path.join(mass_folder, f"{i}.mp4")).duration for i in existing_indices) + 45
        else:
            clip_idx = 1
            start_time = 75.0
        
        while start_time + MIN_CLIP_LENGTH <= end_time:
            # Generate clip
            clip_path = os.path.join(mass_folder, f"{clip_idx}.mp4")
            processed_path = os.path.join(mass_folder, f"{clip_idx}_final.mp4")
            
            # Extract clip with defined start time
            extract_clip(MOVIE_FILE, clip_path, start_time)
            
            print('doing fast cuts')
            dynamic_clip = create_fast_cuts(clip_path)
            dynamic_path = os.path.join(mass_folder, f"{clip_idx}_dynamic.mp4")

            dynamic_clip.write_videofile(dynamic_path, codec="libx264")
            cleanup_clip(dynamic_clip)

            # Transcribe using the saved dynamic clip
            captions, timings = transcribe_audio(dynamic_path)

            #save captions for use with gemini
            captions_file = os.path.join(mass_folder, f"{clip_idx}_captions.txt")
            with open(captions_file, "w", encoding="utf-8") as cf:
                for caption in captions:
                    cf.write(caption)


            # Add captions to the dynamic clip file
            captioned_clip = add_captions(dynamic_path, captions, timings)
            #bleeped_clip = add_bleeps(captioned_clip, captions)
            final_clip = add_music(captioned_clip, get_random_music_file())
            
            # Save result
            final_clip.write_videofile(processed_path, codec="libx264")
            cleanup_clip(final_clip)

            print('generating gemini title/description/tags...')
            short_metadata = try_generate_metadata(captions, MOVIE_FILE)

            meta_file = os.path.join(mass_folder, f"{clip_idx}_short_metadata.json")
            with open(meta_file, "w") as mf:
                json.dump(short_metadata, mf, indent=2)

            # Move to next segment
            with VideoFileClip(clip_path) as clip:
                used_duration = clip.duration
            start_time += used_duration
            clip_idx += 1
            
        print(f"Mass produced {clip_idx-1} clips!")
    else:
        # Generate only one clip
        print('processing a single clip')
        print(sys.argv)
        start_time = random.uniform(0.0, 1200.0)  # Random float between 0.0 and 1200.0 seconds  
    
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
        extract_clip(MOVIE_FILE, clip_file, start_time)

        #clip_file = os.path.join(OUTPUT_FOLDER, "clip_54.mp4")
        print("did it save????")
        
        
        # transcription_file = os.path.join(OUTPUT_FOLDER, "clip_54_transcription.json")
        # with open(transcription_file, 'r') as f:
        #     transcription_data = json.load(f)
        # captions = transcription_data['captions']
        # timings = transcription_data['timings']

        #clip_file = os.path.join(OUTPUT_FOLDER, "clip_54.mp4")
        
        
        fast_cut_clip = create_fast_cuts(clip_file)
        temp_fast_cut_path = os.path.join(OUTPUT_FOLDER, f"clip_{i}_fastcut.mp4")
        fast_cut_clip.write_videofile(temp_fast_cut_path, codec="libx264")
        cleanup_clip(fast_cut_clip)
        # Pass the saved file path into transcribe_audio
        captions, timings = transcribe_audio(temp_fast_cut_path)
        
        print(captions)
        captions_file = os.path.join(OUTPUT_FOLDER, f"clip_{i}_captions.txt")
        with open(captions_file, "w") as cf:
            cf.write(captions)


        print("adding caption...")
        captioned_clip = add_captions(fast_cut_clip, captions, timings)

        final_clip = captioned_clip #add_bleeps(captioned_clip,captions)


        print("before muzax")
        Music_file = get_random_music_file()
        final_clip = add_music(final_clip, Music_file)
        print("Saving final video...")
        final_clip.write_videofile(processed_file, codec="libx264")
        cleanup_clip(final_clip)
        print('generating gemini title/description/tags...')
        
        caption_text = " ".join(captions)  # Join captions for Gemini
        print(caption_text)
        short_metadata = generate_youtube_metadata(caption_text, MOVIE_FILE[:-4], metadata_dir=OUTPUT_FOLDER)
        meta_file = os.path.join(OUTPUT_FOLDER, f"clip_{i}_short_metadata.json")
        with open(meta_file, "w") as mf:
            json.dump(short_metadata, mf, indent=2)


        #music = AudioFileClip(music_file)
        #music.with_effects([afx.MultiplyVolume(0.5)])