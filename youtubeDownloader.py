import os
import sys
import yt_dlp
import json
import subprocess
import tempfile
import re
import requests

def verify_captions(video_file):
    """Verify if captions are present in the video file."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            video_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        subtitle_streams = [
            s for s in data.get('streams', [])
            if s.get('codec_type') == 'subtitle'
        ]
        
        if subtitle_streams:
            print("\nFound subtitle streams in video:")
            for stream in subtitle_streams:
                print(f"  - Codec: {stream.get('codec_name')}")
                print(f"    Language: {stream.get('tags', {}).get('language','unknown')}")
            return True
        else:
            print("\nNo subtitle streams found in video")
            return False
    except Exception as e:
        print(f"Error verifying captions: {e}")
        return False

def extract_srt(video_file, stream_index=0):
    """Extract an SRT file from the embedded subtitle stream."""
    tmp = tempfile.NamedTemporaryFile(suffix='.srt', delete=False)
    cmd = [
        'ffmpeg', '-y', '-i', video_file,
        # map the specific subtitle stream
        '-map', f'0:{stream_index}',
        # explicitly choose SRT codec...
        '-c:s', 'srt',
        # ...and force SRT container format
        '-f', 'srt',
        tmp.name
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ffmpeg error extracting SRT: {res.stderr}")
        return None
    with open(tmp.name, 'r', encoding='utf-8') as f:
        srt_text = f.read()
    os.unlink(tmp.name)
    return srt_text

def parse_srt_to_json(srt_text, out_path):
    """
    Parse SRT text into word-level captions + timings JSON.
    Writes {"captions": [...], "timings": [[start,end], ...]}.
    """
    blocks = re.split(r'\n\n+', srt_text.strip())
    captions, timings = [], []
    
    for block in blocks:
        lines = block.splitlines()
        if len(lines) >= 3:
            start_str, end_str = lines[1].split(' --> ')
            def to_sec(ts):
                h, m, rest = ts.split(':')
                s, ms = rest.split(',')
                return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
            start, end = to_sec(start_str), to_sec(end_str)
            words = ' '.join(lines[2:]).split()
            if not words:
                continue
            dur = (end - start) / len(words)
            for i, w in enumerate(words):
                captions.append(w)
                timings.append([start + i*dur, start + (i+1)*dur])
    
    payload = {"captions": captions, "timings": timings}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote transcript JSON to {out_path}")

def parse_vtt_time(time_str):
    """Convert VTT timestamp to seconds."""
    h, m, s = time_str.split(':')
    s, ms = s.split('.')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def sanitize_filename(title):
    """Convert video title to a valid filename."""
    # Remove invalid filename characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, '')
    # Replace spaces with underscores
    title = title.replace(' ', '_')
    return title

def download_video(url, output_dir="VietnamInput"):
    """Download video and extract captions to JSON."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': False,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        # Download video and get info
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info['title']
            video_path = os.path.join(output_dir, f"{video_title}.mp4")
            
            # Get captions if available
            if 'subtitles' in info or 'automatic_captions' in info:
                captions = []
                timings = []
                
                # Try to get manual captions first, then automatic
                if 'subtitles' in info and 'en' in info['subtitles']:
                    caption_data = info['subtitles']['en']
                elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
                    caption_data = info['automatic_captions']['en']
                else:
                    print("No English captions found")
                    return video_path
                
                # Process captions
                for caption in caption_data:
                    if caption['ext'] == 'vtt':
                        # Download and parse VTT file
                        vtt_url = caption['url']
                        response = requests.get(vtt_url)
                        vtt_content = response.text
                        
                        # Parse VTT content
                        current_text = []
                        current_start = None
                        current_end = None
                        
                        for line in vtt_content.split('\n'):
                            line = line.strip()
                            
                            # Skip header and empty lines
                            if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                                continue
                                
                            # Parse timing line
                            if '-->' in line:
                                if current_text and current_start is not None and current_end is not None:
                                    # Process accumulated text
                                    text = ' '.join(current_text)
                                    words = text.split()
                                    word_count = len(words)
                                    
                                    if word_count > 0:
                                        # Calculate duration per word
                                        duration = current_end - current_start
                                        word_duration = duration / word_count
                                        
                                        # Create timing for each word
                                        for i, word in enumerate(words):
                                            word_start = current_start + (i * word_duration)
                                            word_end = word_start + word_duration
                                            captions.append(word)
                                            timings.append((round(word_start, 3), round(word_end, 3)))
                                    
                                # Reset for next block
                                current_text = []
                                times = line.split(' --> ')
                                if len(times) == 2:
                                    current_start = parse_vtt_timestamp(times[0])
                                    current_end = parse_vtt_timestamp(times[1])
                            else:
                                # Accumulate text
                                current_text.append(line)
                        
                        # Process final block
                        if current_text and current_start is not None and current_end is not None:
                            text = ' '.join(current_text)
                            words = text.split()
                            word_count = len(words)
                            
                            if word_count > 0:
                                duration = current_end - current_start
                                word_duration = duration / word_count
                                
                                for i, word in enumerate(words):
                                    word_start = current_start + (i * word_duration)
                                    word_end = word_start + word_duration
                                    captions.append(word)
                                    timings.append((round(word_start, 3), round(word_end, 3)))
                        
                        break  # Use first VTT format found
                
                # Save captions and timings to JSON
                json_path = os.path.join(output_dir, f"{video_title}.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'transcript': ' '.join(captions),
                        'timings': timings
                    }, f, indent=2)
                
                print(f"Saved captions to {json_path}")
                return video_path
            
            print("No captions found")
            return video_path
            
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        return None

def parse_vtt_timestamp(timestamp):
    """Parse VTT timestamp to seconds."""
    try:
        # Extract just the timestamp part if there's additional metadata
        timestamp = timestamp.split()[0]
        
        # Handle different VTT timestamp formats
        if '.' in timestamp:
            hours, minutes, seconds = timestamp.split(':')
            seconds, milliseconds = seconds.split('.')
        else:
            hours, minutes, seconds = timestamp.split(':')
            milliseconds = '000'
        
        total_seconds = (
            int(hours) * 3600 +
            int(minutes) * 60 +
            int(seconds) +
            int(milliseconds) / 1000
        )
        return round(total_seconds, 3)
    except Exception as e:
        print(f"Error parsing timestamp {timestamp}: {str(e)}")
        return 0.0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python youtubeDownloader.py <YouTube_URL>")
        sys.exit(1)

    video_url = sys.argv[1]
    download_video(video_url)
