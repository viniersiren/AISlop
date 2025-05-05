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

    captions = []
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
                    
                    captions.append(word)
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
            
            captions.append(word)
            timings.append((start, end))
            last_end_time = end

    return " ".join(captions), timings

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

    ORIG_H = 808
    ORIG_OFFSET = 350
    offset_px = ORIG_OFFSET * height / ORIG_H
    y_base = height - int(offset_px)
    current_y = y_base

    current_section = []
    current_timings = []
    words = captions.split()

    # Group words into sections
    for i, (word, timing) in enumerate(zip(words, timings)):
        if timing[1] <= timing[0]:  # Skip invalid timings
            continue
            
        current_section.append(word)
        current_timings.append(timing)
        
        # Break section if next word starts >0.5s after this one ends
        if i < len(words) - 1:
            next_start = timings[i+1][0]
            if next_start - timing[1] > 0.5:
                create_section(clips, current_section, current_timings, current_y, width)
                current_section = []
                current_timings = []

    # Add final section
    if current_section:
        create_section(clips, current_section, current_timings, current_y, width)

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

def main():
    input_video = "output.mp4"
    output_video = "output_with_bounce.mp4"
    transcript_file = "transcript.json"
    temp_clip_path = "temp_clip_30s.mp4"

    # Cut 30s clip and save it
    if not os.path.exists(temp_clip_path):
        print("Saving 30-second preview clip...")
        video = VideoFileClip(input_video).subclipped(0, 30)
        video.write_videofile(temp_clip_path, codec="libx264", audio_codec="aac")
    else:
        video = VideoFileClip(temp_clip_path)

    # Check if transcript already exists
    if os.path.exists(transcript_file):
        with open(transcript_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            transcript = data["transcript"]
            timings = data["timings"]
        print("Loaded transcript from file.")
    else:
        transcript, timings = transcribe_audio(temp_clip_path)
        print("Generated new transcript.")

        with open(transcript_file, "w", encoding="utf-8") as f:
            json.dump({"transcript": transcript, "timings": timings}, f, indent=2)

    print(f"Transcript: {transcript}")
    
    # Add animated captions
    final_clip = add_captions(video, transcript, timings)
    
    # Preserve original audio
    final_clip.audio = video.audio
    
    # Write result
    final_clip.write_videofile(
        output_video,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset='fast',
        ffmpeg_params=['-crf', '23']
    )

def load_transcript_json(json_path):
    """Load transcript data from JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading transcript JSON: {e}")
        return None

def analyze_word_timings(json_path):
    """Analyze and print timing information for each word."""
    try:
        # Load transcript data
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        transcript = data['transcript']
        timings = data['timings']
        
        print("\nWord Animation Timing Analysis:")
        print("=" * 100)
        print(f"{'Word':<15} {'Appears':<10} {'Bounce Start':<12} {'Bounce End':<12} {'Disappears':<12} {'Duration':<10}")
        print("-" * 100)
        
        words = transcript.split()
        for i, (word, timing) in enumerate(zip(words, timings)):
            start, end = timing
            duration = end - start
            
            # Print timing information for each word
            print(f"{word:<15} {start:<10.3f} {start:<12.3f} {end:<12.3f} {end:<12.3f} {duration:<10.3f}")
            
            # Add separator between words
            if i < len(words) - 1:
                next_start = timings[i + 1][0]
                gap = next_start - end
                if gap > 0.5:
                    print("-" * 100)
                    print(f"Section Break: {gap:.3f}s gap")
                    print("-" * 100)
        
        # Print summary
        print("\nSummary:")
        print(f"Total words: {len(words)}")
        print(f"Total duration: {timings[-1][1] - timings[0][0]:.3f} seconds")
        print(f"Average word duration: {sum(end - start for start, end in timings) / len(timings):.3f} seconds")
        
    except Exception as e:
        print(f"Error analyzing timings: {str(e)}")

def process_video_with_captions(input_path, output_path, duration=20):
    """Process video with captions and create a clip of specified duration."""
    try:
        # Load transcript data
        transcript_path = input_path.replace('.mp4', '.json')
        with open(transcript_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Print timing analysis before processing
        print("\nAnalyzing word timings before processing:")
        analyze_word_timings(transcript_path)
        
        # Create video clip
        video = VideoFileClip(input_path)
        clip = video.subclipped(0, duration)
        
        # Filter transcript and timings to only include words within the clip duration
        words = data['transcript'].split()
        timings = data['timings']
        filtered_words = []
        filtered_timings = []
        
        for word, timing in zip(words, timings):
            if timing[0] < duration:
                filtered_words.append(word)
                filtered_timings.append(timing)
        
        # Create captions - pass the filtered words directly without splitting
        captions = add_captions(clip, " ".join(filtered_words), filtered_timings)
        
        # Add captions to video
        final_video = CompositeVideoClip([clip, captions])
        
        # Write output
        final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
        
        # Print timing analysis after processing
        print("\nAnalyzing word timings after processing:")
        analyze_word_timings(transcript_path)
        
        # Cleanup
        video.close()
        final_video.close()
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        raise

if __name__ == "__main__":
    # Example usage
    video_path = "VietnamInput/Wealth Triangle  Are You Rich Enough For Your Age.mp4"
    json_path = "VietnamInput/Wealth Triangle  Are You Rich Enough for Your Age.json"
    output_path = "VietnamInput/Wealth Triangle Are You Rich Enough For Your Age333_captioned.mp4"
    process_video_with_captions(video_path, output_path)