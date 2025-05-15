#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import tempfile
from datetime import datetime
import glob

def extract_subtitles_to_vtt(mp4_path):
    """Extract subtitles from MP4 to VTT format."""
    with tempfile.NamedTemporaryFile(suffix='.vtt', delete=False) as temp_vtt:
        # First try to get subtitle stream info
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 's',
            '-show_entries', 'stream=codec_name',
            '-of', 'json',
            mp4_path
        ]
        try:
            print("Checking for subtitle streams...")
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            streams = json.loads(result.stdout).get('streams', [])
            if not streams:
                print("No subtitle streams found in the file")
                return None
                
            codec = streams[0].get('codec_name', 'unknown')
            print(f"Found subtitle stream with codec: {codec}")
            
            # Get video duration to adjust timeout
            duration_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                mp4_path
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
            duration = float(json.loads(duration_result.stdout)['format']['duration'])
            # Set timeout to 2 minutes per minute of video, with a minimum of 2 minutes
            timeout = max(120, int(duration * 2))
            print(f"Video duration: {duration:.1f} seconds, setting timeout to {timeout} seconds")
            
            # Extract subtitles using mov2textsub
            cmd = [
                'ffmpeg',
                '-i', mp4_path,
                '-map', '0:s:0',
                '-c:s', 'mov_text',
                '-f', 'webvtt',
                temp_vtt.name
            ]
            print("Extracting subtitles (this may take a while for longer videos)...")
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
            print("Subtitle extraction completed")
            return temp_vtt.name
                
        except subprocess.CalledProcessError as e:
            print(f"Error extracting subtitles: {e.stderr.decode() if e.stderr else str(e)}", file=sys.stderr)
            if os.path.exists(temp_vtt.name):
                os.unlink(temp_vtt.name)
            return None
        except subprocess.TimeoutExpired:
            print(f"Subtitle extraction timed out after {timeout} seconds")
            if os.path.exists(temp_vtt.name):
                os.unlink(temp_vtt.name)
            return None
        except Exception as e:
            print(f"Unexpected error during subtitle extraction: {e}", file=sys.stderr)
            if os.path.exists(temp_vtt.name):
                os.unlink(temp_vtt.name)
            return None

def parse_vtt_timestamp(timestamp):
    """Convert VTT timestamp to seconds."""
    try:
        dt = datetime.strptime(timestamp, '%H:%M:%S.%f')
        return dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1000000
    except ValueError:
        return 0

def parse_vtt_file(vtt_path):
    """Parse VTT file and extract words with timings."""
    words = []
    timings = []
    
    try:
        print("Reading VTT file...")
        with open(vtt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        print("Parsing VTT content...")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip header and empty lines
            if not line or line == 'WEBVTT' or '-->' not in line:
                i += 1
                continue
                
            # Parse timestamp line
            if '-->' in line:
                start_time, end_time = line.split(' --> ')
                start_seconds = parse_vtt_timestamp(start_time)
                end_seconds = parse_vtt_timestamp(end_time)
                
                # Get the text line
                i += 1
                while i < len(lines) and lines[i].strip():
                    text = lines[i].strip()
                    # Split into words and add each word with the same timing
                    for word in text.split():
                        # Clean the word
                        word = word.strip('.,!?()[]{}":;')
                        if word:
                            words.append(word.lower())
                            timings.append((start_seconds, end_seconds))
                    i += 1
            i += 1
            
        print(f"Parsed {len(words)} words from VTT file")
            
    except Exception as e:
        print(f"Error parsing VTT file: {e}", file=sys.stderr)
        return None, None
        
    return words, timings

def create_json_from_mp4(mp4_path):
    """Create JSON file from MP4 subtitles."""
    print(f"\nProcessing: {mp4_path}")
    
    # Extract subtitles to VTT
    vtt_path = extract_subtitles_to_vtt(mp4_path)
    if not vtt_path:
        print("No subtitles found in the MP4 file.")
        return False
        
    # Parse VTT file
    words, timings = parse_vtt_file(vtt_path)
    if not words or not timings:
        print("Failed to parse subtitles.")
        os.unlink(vtt_path)
        return False
        
    # Create JSON data
    json_data = {
        "transcript": words,
        "timings": timings
    }
    
    # Save JSON file
    json_path = os.path.splitext(mp4_path)[0] + '.json'
    try:
        print(f"Saving JSON file to: {json_path}")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
        print(f"Successfully created JSON file: {json_path}")
        return True
    except Exception as e:
        print(f"Error saving JSON file: {e}", file=sys.stderr)
        return False
    finally:
        # Clean up temporary VTT file
        os.unlink(vtt_path)

def find_mp4_files(directory):
    """Recursively find all MP4 files in directory and its subdirectories."""
    mp4_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.mp4'):
                mp4_files.append(os.path.join(root, file))
    return mp4_files

def extract_test_clip(input_path, duration=15):
    """Extract a test clip from the middle of the video."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_mp4:
        # Get video duration
        duration_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            input_path
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
        total_duration = float(json.loads(duration_result.stdout)['format']['duration'])
        
        # Calculate start time (middle of video minus half the test duration)
        start_time = (total_duration - duration) / 2
        
        # Extract clip
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',  # Copy streams without re-encoding
            temp_mp4.name
        ]
        print(f"Extracting {duration}-second test clip from {start_time:.1f}s...")
        subprocess.run(cmd, check=True, capture_output=True)
        print("Test clip extracted successfully")
        return temp_mp4.name

def main():
    if len(sys.argv) != 2:
        print("Usage: python jsonMp4Creator.py <directory_path>")
        sys.exit(1)
        
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)
    
    # Find all MP4 files
    mp4_files = find_mp4_files(directory)
    if not mp4_files:
        print(f"No MP4 files found in {directory}")
        sys.exit(1)
    
    print(f"Found {len(mp4_files)} MP4 files")
    
    # Process each MP4 file
    success_count = 0
    for mp4_path in mp4_files:
        try:
            # Extract test clip
            test_clip = extract_test_clip(mp4_path)
            print(f"\nTesting with 15-second clip from: {mp4_path}")
            
            # Try to process the test clip
            if create_json_from_mp4(test_clip):
                print("Test successful! Processing full video...")
                if create_json_from_mp4(mp4_path):
                    success_count += 1
            else:
                print("Test failed - skipping full video")
            
            # Clean up test clip
            os.unlink(test_clip)
            
        except Exception as e:
            print(f"Error processing {mp4_path}: {e}")
            continue
    
    print(f"\nProcessed {len(mp4_files)} files, {success_count} successful")
    sys.exit(0 if success_count > 0 else 1)

if __name__ == '__main__':
    main() 