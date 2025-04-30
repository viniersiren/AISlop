#!/usr/bin/env python3
import os
import subprocess
import sys

def remux_mkv_to_mp4(path):
    """
    Losslessly remux an MKV into MP4 by copying only video & audio streams,
    dropping subtitles to avoid unsupported-codec errors.
    """
    base, _ = os.path.splitext(path)
    mp4_path = f"{base}.mp4"
    cmd = [
        'ffmpeg',
        '-i', path,
        '-map', '0:v',        # map all video streams
        '-map', '0:a',        # map all audio streams
        '-c', 'copy',         # copy codecs without re-encoding
        '-sn',                # disable subtitle streams
        mp4_path
    ]
    print(f"Remuxing: {path} → {mp4_path}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error remuxing {path}: {e}", file=sys.stderr)

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
