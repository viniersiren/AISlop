import os
import glob
import json
import time
import random
import subprocess
import argparse
from youtubeUploader import ensure_vertical_video, upload_to_youtube

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def load_uploaded_indices(uploaded_json_path):
    if os.path.exists(uploaded_json_path):
        with open(uploaded_json_path, "r") as f:
            return set(json.load(f))
    return set()

def save_uploaded_indices(uploaded_json_path, uploaded_indices):
    with open(uploaded_json_path, "w") as f:
        json.dump(sorted(uploaded_indices), f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Process and upload video clips')
    parser.add_argument('video_dir', type=str, help='Directory containing video clips')
    parser.add_argument('--start-from', type=int, default=1, help='Index of video to start processing from (default: 1)')
    parser.add_argument('--count', type=int, default=1, help='Number of videos to upload (default: 1)')
    args = parser.parse_args()

    video_files = glob.glob(os.path.join(args.video_dir, "*_final.mp4"))
    video_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]))

    uploaded_json_path = os.path.join(args.video_dir, "uploaded.json")

    uploaded_indices = load_uploaded_indices(uploaded_json_path)

    # Extract indices from filenames
    available_indices = [
        int(os.path.basename(f).split('_')[0]) for f in video_files
    ]
    # Filter out already uploaded indices
    remaining_indices = list(set(available_indices) - uploaded_indices)

    if not remaining_indices:
        print("No new videos to upload.")
        return

    # Determine how many videos to upload
    num_to_upload = min(args.count, len(remaining_indices))
    selected_indices = random.sample(remaining_indices, num_to_upload)

    for idx in selected_indices:
        input_video = os.path.join(args.video_dir, f"{idx}_final.mp4")
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

        thumbnail_path = os.path.join(args.video_dir, f"thumbnails/thumbnail_{idx}.jpg")
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(random_time), "-i", vertical_path,
            "-vframes", "1", "-q:v", "2", thumbnail_path
        ], check=True)

        meta_path = os.path.join(args.video_dir, f"{idx}_short_metadata.json")
        with open(meta_path, "r") as mf:
            metadata = json.load(mf)
            title = metadata["title"]
            description = metadata["description"]
            tags = metadata.get("tags", [])
            category = metadata.get("category", "24")

        # Upload video with title and description metadata
        upload_to_youtube(vertical_path, title, description, tags)

        # Update uploaded indices
        uploaded_indices.add(idx+1)
        save_uploaded_indices(uploaded_json_path, uploaded_indices)

        # Wait for a random interval between uploads (30 mins to 2 hours)
        wait_time = random.randint(1800, 7200)
        print(f"Waiting for {wait_time // 60} minutes before next upload...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()
