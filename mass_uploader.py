import os
import glob
import time
import random
import subprocess
import argparse
from youtubeUploader import ensure_vertical_video, upload_to_youtube

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
def main():
    parser = argparse.ArgumentParser(description='Process and upload video clips')
    parser.add_argument('video_dir', type=str, help='Directory containing video clips')
    parser.add_argument('--start-from', type=int, default=1, help='Index of video to start processing from (default: 1)')
    args = parser.parse_args()

    video_files = glob.glob(os.path.join(args.video_dir, "*_final.mp4"))
    video_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]))

    for idx, input_video in enumerate(video_files, start=1):
        if idx < args.start_from:
            continue

        base, ext = os.path.splitext(input_video)
        processed_video = f"{base}_vertical{ext}"

        vertical_path = ensure_vertical_video(input_video, processed_video)

        # Generate thumbnail from processed video
        duration_cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', vertical_path
        ]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        random_time = round(random.uniform(1, max(duration - 2, 1)), 2)

        thumbnail_path = f"thumbnails/thumbnail_{idx}.jpg"
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(random_time), "-i", vertical_path,
            "-vframes", "1", "-q:v", "2", thumbnail_path
        ], check=True)

        # Updated What We Do in the Shadows-themed metadata with episode numbering
        title = f"(Part {idx}): Legendary Moments: What We Do in the Shadows | Best Scenes Compilation Short"

        description = f"""Dive into the darkly hilarious world of *What We Do in the Shadows*! Part {idx} of our special series features:

- Vladislav's brooding yet comical moments
- Nadja's seductive mischief and fierce spirit
- Laszlo's eccentric antics and outrageous charm
- Colin Robinson's deadpan encounters with mortals

"Remember, we may be undead, but we’re eternally fabulous!" 

#Shorts #Short #WhatWeDoInTheShadows #WWDITS #VampireComedy #DarkHumor #SitcomHorror #UndeadLife
"""
        # Upload video with title and description metadata
        upload_to_youtube(vertical_path, title, description)

        # Wait for a random interval between uploads (3.5 to 7 minutes)
        wait_time = random.randint(210, 420)
        time.sleep(wait_time)

if __name__ == "__main__":
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    main()