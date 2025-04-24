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

                   
                    captions.append(word)
                    timings.append((start, end))

    # Process final result
    final_result = json.loads(rec.FinalResult())
    if 'result' in final_result:
        for word_info in final_result['result']:
            word = word_info['word']
            start = word_info['start']
            end = word_info['end']

         
            captions.append(word)
            timings.append((start, end))

    return " ".join(captions), timings

def add_captions(video, captions, timings):
    # Debug: Print input parameters
    print(f"Adding captions to video. Captions count: {len(captions.split())}, Timings count: {len(timings)}")
    
    if isinstance(video, str):
        print(f"Loading video from file: {video}")
        video = VideoFileClip(video)
    
    width, height = video.size
    print(f"Video dimensions: {width}x{height}, Duration: {video.duration}s")

    clips = [video]

    ORIG_H = 808
    ORIG_OFFSET = 350

    # compute a scaled offset
    offset_px = ORIG_OFFSET * height / ORIG_H
    y_base = height - int(offset_px)
    #y_base = height - 350  # Starting Y position for captions
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
        if len(current_section) >= 3 or (word.endswith('.') or word.endswith(',')):
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

BOUNCE_FREQUENCY = 10   # Add these constants at the top of your file
RISE_HEIGHT = 5      # how many pixels the word will rise
RISE_DURATION = 0.3     # seconds over which the rise happens

def create_section(clips, words, timings, y_pos, screen_width):
    """Create a non-overlapping section of words with a temporary rise effect, glow, shadow, and color accents."""
    try:
        # Constants
        RISE_HEIGHT = 17  # Define the height words will rise
        RISE_DURATION = 0.5  # Duration of the rise animation
        
        # 1) Filter bleeps
        section = [(w, t) for w, t in zip(words, timings) if w != "[BLEEP]"]
        if not section:
            return
        texts, times = zip(*section)
        
        # 2) Get overall section timing
        section_start = times[0][0]
        section_end = times[-1][1]

        font_size = int(screen_width * 0.05)
        print(font_size)
            # limit each text line to 80% of video width:
        max_w = int(screen_width * 0.8)
        
        # 3) Build TextClips (spanning section duration) so we can measure widths
        clips_info = []
        for word in texts:
            # bold color for long words
            color = "yellow" if len(word) > 5 else "white"
            txt = TextClip(
                text=word,
                font="./premadeTest/shortfarm/fonts/font.ttf",
                font_size     = font_size, 
                color=color,
                stroke_color="black",
                stroke_width=1,
                margin=(0, 5),

            )
            clips_info.append(txt)
        
        # 4) Compute centering + padding
        PADDING = 20
        total_w = sum(txt.w for txt in clips_info) + PADDING * (len(clips_info) - 1)
        x_start = (screen_width - total_w) / 2
        
        # 5) For each word, create shadow, glow, and temporarily risen text
        x = x_start
        for i, (txt, (w_start, w_end)) in enumerate(zip(clips_info, times)):
            # Each clip is visible for the entire section, but animations triggered at word time
            
            # shadow: offset + semi-transparent - visible entire time except when word is spoken
            shadow_normal = (txt
                     .with_position((x + 2, y_pos + 2))
                     .with_start(section_start)
                     .with_end(w_start)  # Only visible until the word's timing starts
                     .with_opacity(0.5))
                     
            shadow_after = (txt
                     .with_position((x + 2, y_pos + 2))
                     .with_start(w_end)  # Visible again after word's timing ends
                     .with_end(section_end)
                     .with_opacity(0.5))
            
            # shadow for risen text - only visible during word timing
            shadow_risen = (txt
                     .with_position((x + 2, y_pos - RISE_HEIGHT + 2))
                     .with_start(w_start)
                     .with_end(w_end)
                     .with_opacity(0.5))
            
            # glow: only appears when word is spoken
            if txt.mask is None:
                glow_color = "yellow" if txt.label.startswith("yellow") else "#aaaaff"  # Light blue glow for white text
                glow_txt = TextClip(
                    text=txt.text,
                    font="./premadeTest/shortfarm/fonts/font.ttf",
                    font_size=font_size,
                    color=glow_color,
                    stroke_color="black",
                    stroke_width=1,
                    margin=(0, 5),

                )
                # Make it slightly larger
                glow_txt = glow_txt.resized(1.05)
            else:
                # Alternative fallback if the above doesn't work
                glow_txt = txt.resized(1.05)
                
            glow = (glow_txt
                   .with_position((x, y_pos - RISE_HEIGHT))  # Position glow at the risen position
                   .with_start(w_start)
                   .with_end(w_end)
                   .with_opacity(0.3))
            
            # Regular text (default position) - visible before and after word timing
            regular_text_before = (txt
                          .with_position((x, y_pos))
                          .with_start(section_start)
                          .with_end(w_start))
                          
            regular_text_after = (txt
                          .with_position((x, y_pos))
                          .with_start(w_end)
                          .with_end(section_end))
            
            # Risen text (only visible during word's time)
            risen_text = (txt
                        .with_position((x, y_pos - RISE_HEIGHT))
                        .with_start(w_start)
                        .with_end(w_end))
            
            clips.extend([shadow_normal, shadow_after, shadow_risen, glow, regular_text_before, regular_text_after, risen_text])
            x += txt.w + PADDING
    
    except Exception as e:
        print(f"Error creating section: {e}")


        # glow = (txt
        #         .with_effects([(color, {"factor": 1.6})])
        #         .resize(1.03)  # slightly enlarges the clip for a glow bleed
        #         .with_opacity(0.2))

        # Create a shadow layer: lower opacity and offset its position.
    #     shadow = txt.with_effect.with_opacity(0.4).with_position(("center", y_pos + 3)) 

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
       
        
def main():
    input_video = "output.mp4"
    output_video = "output_with_bounce.mp4"
    
    # Process first 30 seconds
    video = VideoFileClip(input_video).subclip(0, 30)
    
    # Transcribe audio
    transcript, timings = transcribe_audio(input_video)
    print(f"Transcript: {transcript}")
    
    # Add animated captions
    final_clip = add_captions(video, transcript, timings)
    
    # Preserve original audio
    final_clip.audio = video.audio
    
    # Write result
    final_clip.write_videofile(
        output_video,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset='fast',
        ffmpeg_params=['-crf', '23']
    )

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
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset='fast',
        ffmpeg_params=['-crf', '23']
    )

if __name__ == "__main__":
    main()