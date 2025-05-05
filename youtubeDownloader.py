import os
import sys
import yt_dlp
import json
import subprocess
import tempfile
import re

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
    """Download a video from YouTube and save it to the specified path."""
    try:
        # Ensure VietnamInput directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'skip_download': False,
            'keepvideo': True,
        }

        # First get video info to get the title
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Getting video info from {url}...")
            info = ydl.extract_info(url, download=False)
            video_title = sanitize_filename(info['title'])
            output_path = os.path.join(output_dir, f"{video_title}.mp4")
            ydl_opts['outtmpl'] = output_path

        # Now download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading video: {video_title}")
            ydl.extract_info(url, download=True)

        if not os.path.exists(output_path):
            print(f"Error: Video was not downloaded to {output_path}")
            return False

        print(f"Video downloaded successfully to {output_path}")
        print("Checking for captions...")

        # Attempt to extract from VTT
        words, timings = [], []
        vtt_path = output_path.rsplit('.', 1)[0] + '.en.vtt'
        if os.path.exists(vtt_path):
            print(f"Found VTT file: {vtt_path}")
            with open(vtt_path, 'r', encoding='utf-8') as f:
                vtt_content = f.read()

            # Robust VTT parsing
            blocks = vtt_content.strip().split('\n\n')
            for block in blocks:
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                # look for the timing line
                timing_lines = [l for l in lines if '-->' in l]
                if not timing_lines:
                    continue
                timing_line = timing_lines[0]
                parts = timing_line.split(' --> ', 1)
                if len(parts) != 2:
                    continue
                start = parse_vtt_time(parts[0])
                end   = parse_vtt_time(parts[1])
                # grab everything except the timing line
                text = ' '.join(l for l in lines if l != timing_line)
                word_list = text.split()
                if not word_list:
                    continue
                dur_per_word = (end - start) / len(word_list)
                for i, w in enumerate(word_list):
                    ws = round(start + i * dur_per_word, 3)
                    we = round(ws + dur_per_word, 3)
                    words.append(w)
                    timings.append([ws, we])

        if words and timings:
            print(f"Extracted {len(words)} words from captions")
            transcript_data = {
                "transcript": " ".join(words),
                "timings": timings
            }
            transcript_path = os.path.join(output_dir, f"{video_title}.json")
            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, indent=2)
            print(f"Saved captions to {transcript_path}")
        else:
            print("No captions found in the video")

        return True

    except Exception as e:
        print(f"Error downloading video: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python youtubeDownloader.py <YouTube_URL>")
        sys.exit(1)

    video_url = sys.argv[1]
    download_video(video_url)
