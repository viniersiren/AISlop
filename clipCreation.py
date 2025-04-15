import os
import json
import random
import wave
import subprocess
import numpy as np
import sys
import traceback

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
MOVIE_FILE = "output.mp4"  # Change this to your movie/show file
MIN_CLIP_LENGTH = 30  # Minimum clip length in seconds
MAX_CLIP_LENGTH = 70  # Maximum clip length in seconds
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
                        captions.append(random.choice(CURSE_WORDS))
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
                captions.append(random.choice(CURSE_WORDS))
            else:
                captions.append(word)
            timings.append((start, end))

    return " ".join(captions), timings

def create_fast_cuts(video_file):
    print("\n=== Starting create_fast_cuts ===")
    print(f"Input file: {video_file}")
    
    try:
        clip = VideoFileClip(video_file)
        original_duration = clip.duration
        print(f"[DEBUG] Original clip loaded successfully")
        print(f"[DEBUG] Original duration: {original_duration:.2f}s")
        print(f"[DEBUG] Original dimensions: {clip.w}x{clip.h}")
        print(f"[DEBUG] Original FPS: {clip.fps}")
    except Exception as e:
        print(f"[ERROR] Failed to load video file: {str(e)}")
        raise

    # Constants (make sure these are defined in your code)
    TRANSITION_DURATION = 0.5  # Added for safety, ensure this exists in your code
    SILENCE_THRESHOLD = 0.025
    CHUNK_DURATION = 0.1

    def detect_silent_intervals(clip, threshold=SILENCE_THRESHOLD, chunk_duration=CHUNK_DURATION):
        """Identify silent periods using audio analysis."""
        print("\n=== Detecting silent intervals ===")
        try:
            print(f"[DEBUG] Starting audio analysis...")
            print(f"[DEBUG] Threshold: {threshold}, Chunk duration: {chunk_duration}")
            
            audio = clip.audio.to_soundarray(fps=22050)
            print(f"[DEBUG] Audio array shape: {audio.shape}")
            
            if len(audio.shape) > 1:
                print(f"[DEBUG] Converting stereo to mono")
                audio = audio.mean(axis=1)
                
            sample_rate = 22050
            chunk_size = int(chunk_duration * sample_rate)
            num_chunks = len(audio) // chunk_size
            print(f"[DEBUG] Total chunks: {num_chunks} ({num_chunks * chunk_duration:.2f}s)")

            silent_intervals = []
            current_silence_start = None
            silence_counter = 0

            for i in range(num_chunks):
                chunk = audio[i*chunk_size:(i+1)*chunk_size]
                rms = np.sqrt(np.mean(chunk**2))
                
                if rms < threshold:
                    silence_counter += 1
                    if current_silence_start is None:
                        current_silence_start = i * chunk_duration
                else:
                    if current_silence_start is not None:
                        silent_intervals.append((
                            max(0, current_silence_start - 0.5),
                            min(clip.duration, i * chunk_duration + 0.5)
                        ))
                        current_silence_start = None

            # Add final silence if needed
            if current_silence_start is not None:
                silent_intervals.append((
                    max(0, current_silence_start - 0.5),
                    min(clip.duration, num_chunks * chunk_duration + 0.5)
                ))

            print(f"[DEBUG] Found {len(silent_intervals)} silent intervals")
            print(f"[DEBUG] Total silence duration: {sum(end-start for start,end in silent_intervals):.2f}s")
            print(f"[DEBUG] Silent intervals: {silent_intervals}")
            return silent_intervals
            
        except Exception as e:
            print(f"[ERROR] Audio analysis failed: {str(e)}")
            traceback.print_exc()
            return []

    def split_active_segments(clip, silent_intervals):
        """Create subclips from non-silent portions."""
        print("\n=== Splitting active segments ===")
        try:
            active_segments = []
            last_end = 0
            
            print(f"[DEBUG] Processing {len(silent_intervals)} silent intervals")
            for idx, (start, end) in enumerate(sorted(silent_intervals)):
                print(f"[DEBUG] Interval {idx+1}: {start:.2f}-{end:.2f}")
                if start > last_end:
                    seg = (last_end, start)
                    active_segments.append(seg)
                    print(f"[DEBUG] Added active segment {len(active_segments)}: {seg[0]:.2f}-{seg[1]:.2f}")
                last_end = end
                
            if last_end < clip.duration:
                final_seg = (last_end, clip.duration)
                active_segments.append(final_seg)
                print(f"[DEBUG] Added final segment: {final_seg[0]:.2f}-{final_seg[1]:.2f}")

            total_active = sum(end-start for start,end in active_segments)
            print(f"[DEBUG] Total active duration: {total_active:.2f}s")
            print(f"[DEBUG] Number of active segments: {len(active_segments)}")
            return [clip.subclipped(start, end) for start, end in active_segments]
            
        except Exception as e:
            print(f"[ERROR] Failed to split segments: {str(e)}")
            traceback.print_exc()
            return []

    def create_zoom_effect(segment):
        """Apply smooth variable zoom to a segment."""
        try:
            print(f"\n[DEBUG] Creating zoom effect for {segment.duration:.2f}s segment")
            duration = segment.duration
            zoom_points = [
                random.uniform(0.9, 1.2),
                random.uniform(0.9, 1.2),
                random.uniform(0.9, 1.2)
            ]
            print(f"[DEBUG] Zoom points: {zoom_points}")
            
            zoom_func = lambda t: np.interp(t, [0, duration/2, duration], zoom_points)
            
            print("[DEBUG] Applying resize effect...")
            resized = segment.fx(vfx.resize, zoom_func)
            
            print("[DEBUG] Applying crop...")
            return resized.fx(
                lambda gf, t: gf(t)[
                    int((gf(t).shape[0] - clip.h)/2):int((gf(t).shape[0] + clip.h)/2),
                    int((gf(t).shape[1] - clip.w)/2):int((gf(t).shape[1] + clip.w)/2)
                ]
            )
        except Exception as e:
            print(f"[ERROR] Zoom effect failed: {str(e)}")
            traceback.print_exc()
            return segment

    # Main processing pipeline
    print("\n=== Processing pipeline starts ===")
    try:
        silent_intervals = detect_silent_intervals(clip)
        active_segments = split_active_segments(clip, silent_intervals)
        
        if not active_segments:
            print("[WARNING] No active segments found! Returning original clip")
            print(f"[DEBUG] Final duration: {clip.duration:.2f}s")
            return clip

        print(f"\n=== Processing {len(active_segments)} segments ===")
        processed_segments = []
        for idx, seg in enumerate(active_segments):
            try:
                print(f"\n[DEBUG] Processing segment {idx+1}/{len(active_segments)}")
                print(f"[DEBUG] Segment duration: {seg.duration:.2f}s")
                print(f"[DEBUG] Segment dimensions: {seg.w}x{seg.h}")
                
                # Apply zoom effect
                zoomed = create_zoom_effect(seg)
                print(f"[DEBUG] After zoom: {zoomed.duration:.2f}s")
                
                # Add speed variation
                speed = random.choice([0.95, 1.0, 1.05])
                print(f"[DEBUG] Applying speed factor: {speed}")
                sped_up = zoomed.fx(vfx.speedx, speed)
                print(f"[DEBUG] After speed change: {sped_up.duration:.2f}s")
                
                processed_segments.append(sped_up)
                print(f"[DEBUG] Segment {idx+1} processing complete")
                
            except Exception as e:
                print(f"[ERROR] Failed to process segment {idx+1}: {str(e)}")
                traceback.print_exc()
                processed_segments.append(seg)

        print("\n=== Concatenating segments ===")
        print(f"[DEBUG] Number of segments to concatenate: {len(processed_segments)}")
        total_processed_duration = sum(s.duration for s in processed_segments)
        print(f"[DEBUG] Total raw duration: {total_processed_duration:.2f}s")
        
        final_clip = concatenate_videoclips(
            processed_segments,
            padding=-TRANSITION_DURATION,
            method="compose",
            transition=CompositeVideoClip.dissolve
        )
        
        print("\n=== Final clip details ===")
        print(f"[DEBUG] Final duration: {final_clip.duration:.2f}s")
        print(f"[DEBUG] Final dimensions: {final_clip.w}x{final_clip.h}")
        print(f"[DEBUG] Final FPS: {final_clip.fps}")
        
        # Validation check
        if final_clip.duration <= 0:
            raise ValueError("Invalid final duration - processing failed")
            
        return final_clip

    except Exception as e:
        print(f"[CRITICAL] Processing pipeline failed: {str(e)}")
        traceback.print_exc()
        print("[WARNING] Returning original clip as fallback")
        return clip

def add_captions(video, captions, timings):
    # Debug: Print input parameters
    print(f"Adding captions to video. Captions count: {len(captions.split())}, Timings count: {len(timings)}")
    
    if isinstance(video, str):
        print(f"Loading video from file: {video}")
        video = VideoFileClip(video)
    
    width, height = video.size
    print(f"Video dimensions: {width}x{height}, Duration: {video.duration}s")

    clips = [video]
    y_base = height - 350  # Starting Y position for captions
    #print(y_base)
    y_increment = 0  # Vertical space between sections
    current_y = y_base
    current_section = []
    current_timings = []

    # Group words into sections of 3-5 words
    for i, (word, (start, end)) in enumerate(zip(captions.split(), timings)):
        current_section.append(word)
        current_timings.append((start, end))
        
        # Start new section when we reach 3 words or find natural break
        if len(current_section) >= 4 or (word.endswith('.') or word.endswith(',')):
            print('decided to start a new section')
            create_section(clips, current_section, current_timings, current_y, width)
            current_y -= y_increment
            current_section = []
            current_timings = []

    # Add remaining words in final section
    if current_section:
        create_section(clips, current_section, current_timings, current_y, width)

    print(f"Created {len(clips)-1} text sections")  # Subtract base video
    
    try:
        final_clip = CompositeVideoClip(clips)
        print("Successfully composed video with caption sections")
        return final_clip
    except Exception as e:
        print(f"Error composing video: {str(e)}")
        return video

def create_section(clips, words, timings, y_pos, screen_width):
    """Helper to create a multi-word text section"""
    try:
        # Combine words and handle bleeps
        section_text = []
        for word in words:
            if word == "[BLEEP]":
                #section_text.append("▓"*random.randint(4, 5))
                print('used to cover the bleep')
            else:
                section_text.append(word)
                
        section_str = " ".join(section_text)
        
        # Calculate section timing
        start_time = timings[0][0]
        end_time = timings[-1][1]
        
        # Create text clip with automatic wrapping
        txt = TextClip(
            text=section_str,
            font="./premadeTest/shortfarm/fonts/font.ttf",
            font_size=60,
            color='white',
            stroke_color='black',
            stroke_width=1,
            size=(int(screen_width*0.9), None),  # Allow wrapping
            method='caption'  # Auto-wrap text
        ).with_position(("center", y_pos))\
         .with_start(start_time)\
         .with_end(end_time)
        
        # glow = (txt
        #         .with_effects([(color, {"factor": 1.6})])
        #         .resize(1.03)  # slightly enlarges the clip for a glow bleed
        #         .with_opacity(0.2))

        # Create a shadow layer: lower opacity and offset its position.
    #     shadow = txt.with_opacity(0.4).with_position(("center", y_pos + 3)) 

        #txt = vfx.Rotate(lambda t: 5 * np.sin(t), txt)

    #     txt_group = CompositeVideoClip([glow, shadow, r]) #meant to have glow as the first arg

    #    # txt_group = txt_group.rotate(lambda t: 5 * np.sin(t))


        # Boost contrast
        #txt = vfx.colorx(txt, 1.3)

        # Apply quick fade in and fade out effects
        #txt = txt.fadein(0.3)
        #txt = txt.fadeout(0.3)

        # Set dynamic position with a subtle vertical bounce
        # txt = txt.set_position(lambda t: (
        #     "center", 
        #     y_pos
        # ))
        clips.append(txt)
        print(f"Created section: {section_str} ({start_time:.1f}-{end_time:.1f}s)")

    except Exception as e:
        print(f"Error creating section: {str(e)}")

def get_random_music_file():
    music_folder = "./music"
    music_files = [f for f in os.listdir(music_folder) if f.endswith(".mp3")]
    if not music_files:
        raise Exception("No .mp3 files found in the music folder.")
    return os.path.join(music_folder, random.choice(music_files))

def add_music(video, music_file):
    # Load music and adjust volume
    music = AudioFileClip(music_file)
    
    music = music.with_effects([afx.MultiplyVolume(0.03)])
    
    # Set music duration to match video
    music = music.with_duration(video.duration)

    videoAud1 = video.audio.with_effects([afx.MultiplyVolume(1.3)])
    
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
    if len(sys.argv) > 1 and sys.argv[1] == '3':
        # Mass production mode
        mass_folder = os.path.join(OUTPUT_FOLDER, "mass_produced")
        os.makedirs(mass_folder, exist_ok=True)
        
        # Get source duration
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', MOVIE_FILE
        ]
        duration = float(subprocess.check_output(probe_cmd))
        end_time = duration - 120  # Last 2 minutes
        
        start_time = 2.0  # Start from 15 seconds
        clip_idx = 1
        
        while start_time + MIN_CLIP_LENGTH <= end_time:
            # Generate clip
            clip_path = os.path.join(mass_folder, f"{clip_idx}.mp4")
            processed_path = os.path.join(mass_folder, f"{clip_idx}_final.mp4")
            
            # Extract clip with defined start time
            extract_clip(MOVIE_FILE, clip_path, start_time)
            
            print('doing fast cuts')
            dynamic_clip = create_fast_cuts(clip_path)
            # Process clip
            print('transcribing audio')
            captions, timings = transcribe_audio(clip_path)
            
            captioned_clip = add_captions(dynamic_clip, captions, timings)
            bleeped_clip = add_bleeps(captioned_clip, captions)
            final_clip = add_music(bleeped_clip, get_random_music_file())
            
            # Save result
            final_clip.write_videofile(processed_path, codec="libx264")
            
            # Move to next segment
            with VideoFileClip(clip_path) as clip:
                used_duration = clip.duration
            start_time += used_duration
            clip_idx += 1
            
        print(f"Mass produced {clip_idx-1} clips!")
    else:
        # Generate only one clip
        print('got here')
        start_time = random.uniform(0.0, 1200.0)  # Random float between 0.0 and 1200.0 seconds  
    
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
        extract_clip(MOVIE_FILE, clip_file, start_time)

        #clip_file = os.path.join(OUTPUT_FOLDER, "clip_54.mp4")
        print("did it save????")
        captions, timings = transcribe_audio(clip_file)
        
        # transcription_file = os.path.join(OUTPUT_FOLDER, "clip_54_transcription.json")
        # with open(transcription_file, 'r') as f:
        #     transcription_data = json.load(f)
        # captions = transcription_data['captions']
        # timings = transcription_data['timings']

        #clip_file = os.path.join(OUTPUT_FOLDER, "clip_54.mp4")
        
        print('creating fast cuts')

        fast_cut_clip = create_fast_cuts(clip_file)

        print("adding caption...")
        captioned_clip = add_captions(fast_cut_clip, captions, timings)

        print("adding bleep sounds...")
        final_clip = add_bleeps(captioned_clip,captions)

        print("before muzax")
        Music_file = get_random_music_file()
        final_clip = add_music(final_clip, Music_file)
        print("Saving final video...")
        final_clip.write_videofile(processed_file, codec="libx264")

        print("Uploading to YouTube...")
        #upload_to_youtube(processed_file, f"AI-Generated Clip {i+1}", "Automatically generated movie/show clip")

        print("Clip processed and uploaded!")



        #music = AudioFileClip(music_file)
        #music.with_effects([afx.MultiplyVolume(0.5)])