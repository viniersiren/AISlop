import os
import glob
import json
import time
import random
import argparse
from youtubeUploader import ensure_vertical_video, upload_to_youtube

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]
CLIENT_SECRETS_DEFAULT = "client_secrets.json"

def load_uploaded_indices(uploaded_json_path):
    if os.path.exists(uploaded_json_path):
        with open(uploaded_json_path, "r") as f:
            return set(json.load(f))
    return set()

def save_uploaded_indices(uploaded_json_path, uploaded_indices):
    with open(uploaded_json_path, "w") as f:
        json.dump(sorted(list(uploaded_indices)), f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Mass upload shorts from specified folder')
    parser.add_argument('--count', type=int, default=1, help='Number of videos to upload per folder')
    parser.add_argument('--client-secrets', default=CLIENT_SECRETS_DEFAULT)
    parser.add_argument('--scopes', nargs='+', default=DEFAULT_SCOPES)
    parser.add_argument('--folder', type=str, required=True, help='The folder name to process')
    args = parser.parse_args()

    folder = args.folder
    print(f"\nProcessing folder: {folder}")
    base_name = folder[:-5] if folder.endswith("Input") else folder
    clips_dir = os.path.join("clips", f"{base_name}Input")

    if not os.path.isdir(clips_dir):
        print(f"  skip, no clips dir {clips_dir}")
        return

    uploaded_json = os.path.join(clips_dir, "uploaded.json")
    uploaded = load_uploaded_indices(uploaded_json)

    # Gather all _final.mp4 files in subdirectories
    video_files = glob.glob(os.path.join(clips_dir, "*", "*_final.mp4"))
    video_files.sort(key=lambda x: int(os.path.basename(x).split("_")[0]))

    # Map compound keys for uniqueness: SubfolderName/Index
    all_videos = []
    for path in video_files:
        subfolder = os.path.basename(os.path.dirname(path))
        index = os.path.basename(path).split("_")[0]
        compound_key = f"{subfolder}/{index}"
        all_videos.append((compound_key, path, subfolder, index))

    remaining_videos = [v for v in all_videos if v[0] not in uploaded]
    if not remaining_videos:
        print("  no new videos to upload")
        return

    to_upload = random.sample(remaining_videos, min(args.count, len(remaining_videos)))

    for compound_key, input_mp4, subfolder, index in to_upload:
        vertical_mp4 = os.path.join(clips_dir, subfolder, f"{index}_final_vertical.mp4")
        vertical = ensure_vertical_video(input_mp4, vertical_mp4)

        meta_json = os.path.join(clips_dir, subfolder, f"{index}_short_metadata.json")
        if not os.path.exists(meta_json):
            print(f"  missing metadata for {compound_key}, skip")
            continue

        with open(meta_json, 'r') as mf:
            meta = json.load(mf)

        short_metadata = meta.get("SHORT_METADATA")
        if short_metadata:
            title = short_metadata.get("title")
            description = short_metadata.get("description")
            tags = short_metadata.get("tags", [])
            category = short_metadata.get("category", 24)  # Default to 24 if category is missing
        else:
            print(f"  missing 'SHORT_METADATA' in metadata for {compound_key}, skipping upload")
            continue

        upload_to_youtube(
            vertical,
            title,
            description,
            tags,
            thumbnail_path=None,
            channel=folder,
            token_path=None,
            scopes=args.scopes,
            client_secrets=args.client_secrets
        )

        uploaded.add(compound_key)
        save_uploaded_indices(uploaded_json, uploaded)
        print(f"  uploaded and recorded {compound_key}")

        wait_sec = random.randint(18000, 30000)
        print(f"  sleeping for {wait_sec // 60}m")
        time.sleep(wait_sec)

if __name__ == "__main__":
    main()