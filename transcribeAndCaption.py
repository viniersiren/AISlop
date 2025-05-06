import re
import traceback
import os
import random
import numpy as np
import sys
import subprocess
import tempfile
import wave
import json
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
VOSK_MODEL_PATH = "models/vosk-model-en-us-0.22"

from vosk import Model, KaldiRecognizer




def transcribe_audio(video_file):
    """Transcribe audio using Vosk with accurate word timing."""
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

    words = []
    timings = []
    last_end_time = 0.0

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if 'result' in result:
                for word_info in result['result']:
                    word = word_info['word']
                    start = round(word_info['start'], 3)
                    end = round(word_info['end'], 3)
                    
                    # Ensure no overlapping timings
                    if start < last_end_time:
                        start = last_end_time
                    if end <= start:
                        end = start + 0.1  # Minimum duration
                    
                    words.append(word)
                    timings.append((start, end))
                    last_end_time = end

    # Process final result
    final_result = json.loads(rec.FinalResult())
    if 'result' in final_result:
        for word_info in final_result['result']:
            word = word_info['word']
            start = round(word_info['start'], 3)
            end = round(word_info['end'], 3)
            
            # Ensure no overlapping timings
            if start < last_end_time:
                start = last_end_time
            if end <= start:
                end = start + 0.1  # Minimum duration
            
            words.append(word)
            timings.append((start, end))
            last_end_time = end

    return words, timings

def add_captions(video, captions, timings):
    """
    Add captions to video with precise timing for each word.
    Words are grouped into sections when there's a gap >0.5s between them.
    """
    print(f"Adding captions to video. Captions count: {len(captions.split())}, Timings count: {len(timings)}")
    
    if isinstance(video, str):
        print(f"Loading video from file: {video}")
        video = VideoFileClip(video)
    
    width, height = video.size
    print(f"Video dimensions: {width}x{height}, Duration: {video.duration}s")

    clips = [video.copy()]

    #shifted = [(start + offset, end + offset) for (start, end) in timings]

    ORIG_H = 808
    ORIG_OFFSET = 350
    offset_px = ORIG_OFFSET * height / ORIG_H
    y_base = height - int(offset_px)
    current_y = y_base

    current_section = []
    current_timings = []
    words = captions.split()

    # Group words into sections
    i = 0
    while i < len(words):
        # Choose a random section size between 3 and 5
        section_size = random.randint(3, 5)
        section_words = words[i:i+section_size]
        section_timings = timings[i:i+section_size]
        create_section(clips, section_words, section_timings, current_y, width)
        i += section_size


    print(f"Created {len(clips)-1} text sections")

    try:
        final = CompositeVideoClip(clips)
        if video.audio is not None:
            final = final.with_audio(video.audio)
        print("Successfully composed video with caption sections")
        return final
    except Exception as e:
        print(f"Error composing video: {e}")
        traceback.print_exc()
        return video

BOUNCE_FREQUENCY = 10   # Add these constants at the top of your file
RISE_HEIGHT = 5      # how many pixels the word will rise
RISE_DURATION = 0.01     # seconds over which the rise happens

def create_section(clips, words, timings, y_pos, screen_width):
    """
    Create a section of words with precise timing for each word's appearance and bounce animation.
    Each word has exactly three states:
    1. Normal position (before and after spoken)
    2. Bounced position (during spoken)
    3. Shadow for each state
    """
    try:
        FONT_PATH = "Raleway-BoldItalic.ttf"
        font_size = int(screen_width * 0.05)
        PADDING = 20
        MAX_W = screen_width * 0.8
        RISE_HEIGHT = 17

        # Filter out bleeps and invalid timings
        section = [(w, t) for w, t in zip(words, timings) if w != "[BLEEP]" and t[1] > t[0]]
        if not section:
            return

        texts, times = zip(*section)
        section_start = times[0][0]
        section_end = times[-1][1]

        # Build TextClips
        clips_info = []
        for w, (start, end) in zip(texts, times):
            txt = TextClip(
                text=w,
                font=FONT_PATH,
                font_size=font_size,
                color="yellow" if len(w) > 5 else "white",
                stroke_color="black",
                stroke_width=1,
                margin=(0, 5),
            )
            if txt.w > 0:
                clips_info.append((txt, (start, end)))

        if not clips_info:
            return

        # Calculate total width and center position
        total_w = sum(t[0].w for t in clips_info) + PADDING * (len(clips_info) - 1)
        if total_w > MAX_W:
            mid = len(clips_info) // 2
            create_section(clips, words[:mid], timings[:mid], y_pos, screen_width)
            create_section(clips, words[mid:], timings[mid:], y_pos, screen_width)
            return

        x = (screen_width - total_w) / 2

        # Create clips for each word
        for txt, (w_start, w_end) in clips_info:
            x0 = max(0, int(x))
            x1 = min(screen_width, int(x + txt.w))
            if x1 <= x0:
                x += txt.w + PADDING
                continue

            # Create the three states for each word
            word_clips = []

            # 1. Normal position (before spoken)
            word_clips.extend([
                # Shadow
                txt.with_position((x0+2, y_pos+2))
                   .with_start(section_start)
                   .with_end(w_start)
                   .with_opacity(0.5),
                # Text
                txt.with_position((x0, y_pos))
                   .with_start(section_start)
                   .with_end(w_start)
            ])

            # 2. Bounced position (during spoken)
            word_clips.extend([
                # Shadow
                txt.with_position((x0+2, y_pos-RISE_HEIGHT+2))
                   .with_start(w_start)
                   .with_end(w_end)
                   .with_opacity(0.5),
                # Glow
                TextClip(text=txt.text, font=FONT_PATH, font_size=font_size,
                        color=txt.color, stroke_color="black", stroke_width=1,
                        margin=(0, 5))
                   .resized(1.05)
                   .with_position((x0, y_pos-RISE_HEIGHT))
                   .with_start(w_start)
                   .with_end(w_end)
                   .with_opacity(0.3),
                # Text
                txt.with_position((x0, y_pos-RISE_HEIGHT))
                   .with_start(w_start)
                   .with_end(w_end)
            ])

            # 3. Normal position (after spoken)
            word_clips.extend([
                # Shadow
                txt.with_position((x0+2, y_pos+2))
                   .with_start(w_end)
                   .with_end(section_end)
                   .with_opacity(0.5),
                # Text
                txt.with_position((x0, y_pos))
                   .with_start(w_end)
                   .with_end(section_end)
            ])

            clips.extend(word_clips)
            x += txt.w + PADDING

    except Exception as e:
        print(f"Error creating section: {e}")
        traceback.print_exc()


def load_transcript_json(json_path):
    """Load transcript data from JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading transcript JSON: {e}")
        return None


def process_video_with_captions(input_path, output_path, duration=10):
    """Process video with captions and create a clip of specified duration."""
    try:
        # Load transcript data
        transcript_path = input_path.replace('.mp4', '.json')
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                words = data['transcript']
                timings = data['timings']
                print("Loaded transcript from JSON file")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Could not load JSON transcript: {e}")
            print("Falling back to Vosk transcription...")
            words, timings = transcribe_audio(input_path)
            print("Completed Vosk transcription")
        
        USE_STATIC_OFFSET = False
        STATIC_OFFSET = -0.4
        if not USE_STATIC_OFFSET:
            dyn_offset = estimate_dynamic_offset(input_path, timings)
        else:
            dyn_offset = STATIC_OFFSET

        # Apply offset to all timings
        adjusted_timings = [
            (max(0, start + dyn_offset), end + dyn_offset)
            for start, end in timings
        ]
        # Create video clip
        video = VideoFileClip(input_path)
        clip = video.subclipped(0, duration)
        
        # Filter transcript and timings to only include words within the clip duration
        filtered_words = []
        filtered_timings = []
        
        for word, timing in zip(words, adjusted_timings):
            if timing[0] < duration:
                filtered_words.append(word)
                filtered_timings.append(timing)

        # Now pass the filtered, adjusted timings into add_captions
        captions = add_captions(clip, " ".join(filtered_words), filtered_timings)
        
        # Add captions to video
        final_video = CompositeVideoClip([clip, captions])
        
        # Write output
        final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
        
        # Cleanup
        video.close()
        final_video.close()
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        raise

def estimate_dynamic_offset(video_file, transcript_timings, vosk_model_path=VOSK_MODEL_PATH):
    """
    Compute a dynamic offset by comparing the first word
    timestamp from the existing transcript_timings vs.
    VOSK's own detection on the video audio.
    """
    # 1) Extract audio to WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        ffmpeg_cmd = [
            'ffmpeg','-y','-i', video_file,
            '-vn','-acodec','pcm_s16le','-ar','16000','-ac','1', tmp.name
        ]
        subprocess.run(ffmpeg_cmd, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wav_path = tmp.name

    # 2) Run VOSK recognizer
    wf = wave.open(wav_path, 'rb')
    os.unlink(wav_path)
    model = Model(vosk_model_path)
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    first_vosk_start = None
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            if 'result' in res and res['result']:
                first_vosk_start = round(res['result'][0]['start'], 3)
                break
    if first_vosk_start is None:
        # Fall back to final chunk if nothing yet
        final = json.loads(rec.FinalResult())
        if 'result' in final and final['result']:
            first_vosk_start = round(final['result'][0]['start'], 3)

    # 3) Compare to your transcript_timings[0][0]
    if first_vosk_start is not None and transcript_timings:
        original_start = transcript_timings[0][0]
        print(first_vosk_start)
        return first_vosk_start - original_start

    return 0.0

if __name__ == "__main__":
    # Example usage
    video_path = "VietnamInput/This dude is a real one for standing up to Kick Streamer Vitaly for disrespecting Filipinos 🇵🇭.mp4"
    json_path = "VietnamInput/This dude is a real one for standing up to Kick Streamer Vitaly for disrespecting Filipinos 🇵🇭.json"
    output_path = "VietnamInput/This dude is a real one for standing up to Kick Streamer Vitaly for disrespecting Filipinos 🇵🇭333_captioned.mp4"
    process_video_with_captions(video_path, output_path)