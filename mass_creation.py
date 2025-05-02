# mass_creation.py
import os
import re
import subprocess
import argparse
import sys

# Directories
INPUT_ROOT = './'
OUTPUT_ROOT = './clips'
# Pattern: folders starting with uppercase and ending with 'Input'
PATTERN = re.compile(r'^[A-Z].*Input$')
# Name of the record file inside each input folder
RECORD_FILENAME = 'processed_clips.txt'


def find_input_folders(root):
    return [os.path.join(root, d) for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d)) and PATTERN.match(d)]


def load_processed(record_path):
    if not os.path.exists(record_path):
        return set()
    with open(record_path, 'r') as f:
        return set(line.strip() for line in f)


def save_processed(record_path, entries):
    with open(record_path, 'a') as f:
        for e in entries:
            f.write(e + '\n')

def process_video(in_path, out_folder):
    cmd = [
        sys.executable, 'clipCreation.py', '3',
        '--input', in_path,
        '--output', out_folder
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error processing {in_path}: {e}")
        return False
    except KeyboardInterrupt:
        print(f"Processing of {in_path} was canceled.")
        return False

def main():
    # Ensure output root exists
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    folders = find_input_folders(INPUT_ROOT)
    for inp in folders:
        rec_file = os.path.join(inp, RECORD_FILENAME)
        processed = load_processed(rec_file)
        candidates = [f for f in os.listdir(inp) if f.lower().endswith('.mp4')]
        to_run = [f for f in candidates if f not in processed]
        if not to_run:
            print(f"No new files in {inp}")
            continue
        print('ddd')
        out_folder = os.path.join(OUTPUT_ROOT, os.path.basename(inp))
        os.makedirs(out_folder, exist_ok=True)

        new_processed = []
        for fname in to_run:
            in_path = os.path.join(inp, fname)
            if process_video(in_path, out_folder):
                new_processed.append(fname)
                os.remove(in_path)  # Delete the original video file after successful processing

        if new_processed:
            save_processed(rec_file, new_processed)
            print(f"Recorded {len(new_processed)} entries in {rec_file}")

if __name__ == '__main__':
    main()
