import os
import glob
import json
import time
import random
import subprocess
import argparse
from youtubeUploader import ensure_vertical_video, upload_to_youtube

#SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]
CLIENT_SECRETS_DEFAULT = "token_secrets.json"

def load_uploaded_indices(uploaded_json_path):
    if os.path.exists(uploaded_json_path):
        with open(uploaded_json_path, "r") as f:
            return set(json.load(f))
    return set()

def save_uploaded_indices(uploaded_json_path, uploaded_indices):
    with open(uploaded_json_path, "w") as f:
        json.dump(sorted(list(uploaded_indices)), f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Mass upload shorts from multiple folders')
    parser.add_argument('--count', type=int, default=1, help='Number of videos to upload per folder')
    parser.add_argument('--client-secrets', default=CLIENT_SECRETS_DEFAULT)
    parser.add_argument('--scopes', nargs='+', default=DEFAULT_SCOPES)
    args = parser.parse_args()

    folders = [d for d in os.listdir('.') if os.path.isdir(d) and d[0].isupper()]

    for folder in folders:
        print(f"\nProcessing folder: {folder}")
        # Remove 'Input' suffix if it’s already there, then re-append it
        base_name = folder[:-5] if folder.endswith("Input") else folder #remove Input when looking into ./clips
        clips_dir = os.path.join("clips", f"{base_name}")
        if not os.path.isdir(clips_dir):
            print(f"  skip, no clips dir {clips_dir}")
            continue

        # Now there’s an extra layer of subfolders inside, each containing videos
        # e.g. clips/AvengersInput/SomeSubfolder/3_final.mp4
        video_files = glob.glob(os.path.join(clips_dir, "*", "*_final.mp4"))
        video_files.sort(key=lambda x: int(os.path.basename(x).split("_")[0]))

        uploaded_json = os.path.join(clips_dir, "uploaded.json")
        uploaded = load_uploaded_indices(uploaded_json)

        available = [int(os.path.basename(f).split('_')[0]) for f in video_files]
        remaining = list(set(available) - uploaded)
        if not remaining:
            print("  no new videos to upload")
            continue

        to_upload = random.sample(remaining, min(args.count, len(remaining)))
        for idx in to_upload:
            input_mp4 = os.path.join(clips_dir, f"{idx}_final.mp4")
            vertical_mp4 = os.path.join(clips_dir, f"{idx}_final_vertical.mp4")
            vertical = ensure_vertical_video(input_mp4, vertical_mp4)

            meta_json = os.path.join(clips_dir, f"{idx}_short_metadata.json")
            if not os.path.exists(meta_json):
                print(f"  missing metadata for {idx}, skip")
                continue

            with open(meta_json, 'r') as mf:
                meta = json.load(mf)

            # call the new uploader
            upload_to_youtube(
                vertical,
                meta["title"],
                meta["description"],
                meta.get("tags", []),
                thumbnail_path=None,
                channel=folder,
                token_path=None,
                scopes=args.scopes,
                client_secrets=args.client_secrets
            )

            uploaded.add(idx)
            save_uploaded_indices(uploaded_json, uploaded)
            print(f"  uploaded and recorded {idx}")

            wait_sec = random.randint(7200, 14000)
            print(f"  sleeping for {wait_sec//60}m")
            time.sleep(wait_sec)

if __name__ == "__main__":
    main()