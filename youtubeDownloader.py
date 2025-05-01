import os
import sys
import yt_dlp

def download_video(url, output_folder='Vietnam'):
    # Ensure the output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Define yt-dlp options
    ydl_opts = {
        'format': 'bv*[height<=1440]+ba/b[height<=1440]',
        'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'postprocessor_args': ['-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental'],
        'noplaylist': True,  # Ensure only single video is downloaded
        'quiet': False,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading video from: {url}")
            ydl.download([url])
            print("Download and merge completed successfully.")
    except yt_dlp.utils.DownloadError as e:
        print(f"Download error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python youtube_downloader.py <YouTube_URL>")
    else:
        video_url = sys.argv[1]
        download_video(video_url)
