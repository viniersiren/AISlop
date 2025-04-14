import os
import glob
import time
import random
import subprocess
from youtubeUploader import ensure_vertical_video, upload_to_youtube

def main():
    video_dir = "./clips/mass_produced"
    video_files = glob.glob(os.path.join(video_dir, "*_final.mp4"))
    video_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]))

    for idx, input_video in enumerate(video_files, start=1):
        base, ext = os.path.splitext(input_video)
        processed_video = f"{base}_vertical{ext}"
        
        vertical_path = ensure_vertical_video(input_video, processed_video)
        
        # Generate thumbnail from processed video
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', vertical_path]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        random_time = round(random.uniform(1, max(duration - 2, 1)), 2)
        
        thumbnail_path = f"thumbnails/thumbnail_{idx}.jpg"
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(random_time), "-i", vertical_path,
            "-vframes", "1", "-q:v", "2", thumbnail_path
        ], check=True)
        
        # Updated HIMYM-themed metadata with episode numbering
        title = f"(Part {idx}): Legendary Moments: How I Met Your Mother  | Best Scenes Compilation Short"
        description = f"""Relive the magic of MacLaren's Pub with these iconic HIMYM moments! Part {idx} of our special series includes:
        
- Ted's most cringe-worthy dating stories
- Barney's legendary plays from the Playbook
- Marshall & Lily's adorable relationship goals
- Robin's Canadian celebrity throwbacks

"Whenever I'm sad, I stop being sad and be awesome instead!" - Barney Stinson

#Shorts #Short #HowIMetYourMother #HIMYM #SitcomClassics #NeilPatrickHarris #BarneyStinson #TedMosby #CBSComedy #BroCode #PuzzlesTheGame"""

        upload_to_youtube(vertical_path, title, description)
        
        wait_time = random.randint(210, 420)  # 3.5 to 7 minutes in seconds
        time.sleep(wait_time)

if __name__ == "__main__":
    main()