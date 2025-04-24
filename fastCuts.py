import traceback
import os
import random
import numpy as np
import sys

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
    #MultiplySpeed,
)

# Constants
#.006, .20
# used to be 0.15, 0.3
TRANSITION_DURATION = 0.31  # seconds
SILENCE_THRESHOLD = 0.15 #.25 is too much, .01 is too little with chunk duration of 0.1
CHUNK_DURATION = 0.30


def detect_silent_intervals(clip, threshold=SILENCE_THRESHOLD, chunk_duration=CHUNK_DURATION):
    """Identify silent periods using audio analysis."""
    try:
        audio = clip.audio.to_soundarray(fps=22050)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        sample_rate = 22050
        chunk_size = int(chunk_duration * sample_rate)
        num_chunks = len(audio) // chunk_size
        print('HEREHERE')
        
        global_rms = np.sqrt((audio**2).mean())
        print(global_rms)
        threshold = global_rms * SILENCE_THRESHOLD
        print(threshold)
        silent_intervals = []
        current_start = None

        for i in range(num_chunks):
            chunk = audio[i*chunk_size:(i+1)*chunk_size]
            rms = np.sqrt((chunk**2).mean())

            if rms < threshold:
                if current_start is None:
                    current_start = i * chunk_duration
            else:
                if current_start is not None:
                    start = max(0, current_start - TRANSITION_DURATION)
                    end = min(clip.duration, i * chunk_duration + TRANSITION_DURATION)
                    silent_intervals.append((start, end))
                    current_start = None

        # Final silence
        if current_start is not None:
            start = max(0, current_start - TRANSITION_DURATION)
            end = min(clip.duration, num_chunks * chunk_duration + TRANSITION_DURATION)
            silent_intervals.append((start, end))

        return silent_intervals
    except Exception as e:
        traceback.print_exc()
        return []


def split_active_segments(clip, silent_intervals):
    """Extract non-silent segments from the clip."""
    active_segments = []
    last_end = 0
    for start, end in sorted(silent_intervals):
        if start > last_end:
            active_segments.append((last_end, start))
        last_end = end
    if last_end < clip.duration:
        active_segments.append((last_end, clip.duration))
    return [clip.subclipped(s, e) for s, e in active_segments]


def create_zoom_effect(segment, target_w, target_h):
    """Apply smooth zoom effect and center-crop back to original resolution."""
    dur = segment.duration
    zoom_vals = [random.uniform(0.9, 1.2) for _ in range(3)]

    # Interpolated zoom function
    def zoom_func(t):
        return np.interp(t, [0, dur/2, dur], zoom_vals)

    # Apply resizing
    #videofileclip
    zoom = random.uniform(0.9, 1.2)
    zoomed = segment.with_effects([vfx.Resize(lambda t: (zoom_func(t) * target_w, zoom_func(t) * target_h))])

    print(type(zoomed))

    # Center-crop using built-in crop effect
    # cropped = vfx.Crop(
    #     zoomed,
    #     width=target_w,
    #     height=target_h,
    #     x_center=segment.w / 2,
    #     y_center=segment.h / 2
    # )
    cropped = zoomed.with_effects([
        vfx.Crop(width=target_w, height=target_h, x_center=segment.w / 2, y_center=segment.h / 2)
    ])

    return cropped


def create_fast_cuts(video_file):
    print(f"Processing {video_file}")
    clip = VideoFileClip(video_file)
    print("Audio object:", clip.audio)
    clip.audio.write_audiofile("test_audio.wav")

    # Detect silent intervals and split into active clips
    silences = detect_silent_intervals(clip)
    segments = split_active_segments(clip, silences)

    # Filter out segments that are too short
    MIN_SEGMENT_DURATION = 0.2
    segments = [s for s in segments if s.duration >= MIN_SEGMENT_DURATION]

    if not segments:
        return clip

    processed = []
    for seg in segments:
        speed = random.choice([0.95, 1.0, 1.05])
        speed_clip = seg.with_effects([vfx.MultiplySpeed(speed)])
        processed.append(speed_clip)

    # No transitions
    final_clips = processed

    final = concatenate_videoclips(final_clips, method="compose")
    
    return final




if __name__ == "__main__":
    input_file = "./clips/mass_produced/27_final.mp4"
    if not os.path.isfile(input_file):
        print(f"[ERROR] Input file not found: {input_file}")
        sys.exit(1)

    result = create_fast_cuts(input_file)
    print(f"[MAIN] create_fast_cuts returned clip: duration={result.duration}, audio={result.audio}")

    # Preview first few seconds
    # duration = min(4, result.duration)
    # preview = result.subclipped(0, duration)
    # if result.audio:
    #     preview = preview.with_audio(result.audio.subclipped(0, duration))
    # else:
    #     print('no audio')
    # print(f"[MAIN] Preview clip: duration={preview.duration}, audio={preview.audio}")

    output_file = "fast27_cuts_preview.mp4"
    # turn on verbose logging to see ffmpeg audio steps
    result.write_videofile(
        output_file,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        audio=True,
        #verbose=True,
        logger="bar"
    )
    print(f"[MAIN] Saved preview: {output_file}")
