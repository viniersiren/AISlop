#!/usr/bin/env python3
import os
import subprocess
import sys
import json

def get_media_info(path):
    """Get detailed information about the media file including available streams."""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error getting media info for {path}: {e}", file=sys.stderr)
        return None

def print_caption_info(media_info):
    """Print information about available caption tracks."""
    if not media_info:
        return
    
    caption_streams = [s for s in media_info.get('streams', []) 
                      if s.get('codec_type') == 'subtitle']
    
    if not caption_streams:
        print("No caption tracks found in the file.")
        return
    
    print("\nAvailable Caption Tracks:")
    for i, stream in enumerate(caption_streams, 1):
        codec = stream.get('codec_name', 'unknown')
        lang = stream.get('tags', {}).get('language', 'unknown')
        title = stream.get('tags', {}).get('title', '')
        print(f"{i}. Format: {codec.upper()}, Language: {lang}, Title: {title}")

def remux_mkv_to_mp4(path):
    """
    Remux an MKV into MP4 with high quality settings and caption detection.
    """
    base, _ = os.path.splitext(path)
    mp4_path = f"{base}.mp4"
    
    # Get media info and print caption information
    print(f"\nAnalyzing: {path}")
    media_info = get_media_info(path)
    print_caption_info(media_info)
    
    # Build ffmpeg command with high quality settings
    cmd = [
        'ffmpeg',
        '-i', path,
        '-map', '0:v',        # map all video streams
        '-map', '0:a',        # map all audio streams
        '-map', '0:s?',       # map all subtitle streams if they exist
        '-c:v', 'copy',       # copy video codec without re-encoding
        '-c:a', 'aac',        # convert audio to AAC
        '-c:s', 'mov_text',   # convert subtitles to MP4-compatible format
        '-b:a', '384k',       # high audio bitrate
        '-movflags', '+faststart',  # enable fast start for web playback
        '-preset', 'medium',   # encoding preset (slower = better quality)
        '-crf', '18',         # constant rate factor (lower = better quality, 18 is visually lossless)
        mp4_path
    ]
    
    print(f"\nRemuxing: {path} → {mp4_path}")
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully remuxed: {path}")
        #os.remove(path)  # Delete the original MKV file
        #print(f"Deleted original MKV file: {path}")
    except subprocess.CalledProcessError as e:
        print(f"Error remuxing {path}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)

def find_and_remux(base_dir, max_depth=3):
    """
    Search up to max_depth levels under base_dir for .mkv files.
    For each .mkv without a same-named .mp4, call remux_mkv_to_mp4().
    """
    base_parts = base_dir.rstrip(os.sep).split(os.sep)
    for root, dirs, files in os.walk(base_dir):
        depth = len(root.split(os.sep)) - len(base_parts)
        if depth > max_depth:
            dirs[:] = []
            continue

        for fname in files:
            if not fname.lower().endswith('.mkv'):
                continue
            mkv_path = os.path.join(root, fname)
            mp4_path = os.path.splitext(mkv_path)[0] + '.mp4'
            if not os.path.exists(mp4_path):
                remux_mkv_to_mp4(mkv_path)

def main():
    # optional arg: directory to scan (defaults to current directory)
    target_root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    if not os.path.isdir(target_root):
        print(f"Error: '{target_root}' is not a directory")
        sys.exit(1)

    # Scan immediate subfolders starting with a capital letter
    for entry in os.listdir(target_root):
        full_path = os.path.join(target_root, entry)
        if os.path.isdir(full_path) and entry[:1].isupper():
            print(f"Scanning folder: {entry}")
            find_and_remux(full_path, max_depth=3)

if __name__ == '__main__':
    main()
