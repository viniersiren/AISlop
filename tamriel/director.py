import os
import json
import subprocess
import datetime
from pathlib import Path
import youtubeUploader
from captionVideo import add_captions_to_video

# Constants
LORECONTENTGEN_PATH = "loreContentGen.py"
EDGETTSGEN_PATH = "edgeTTSGenerator.py"
VIDEOCREATION_PATH = "videoCreation.py"
TRACKING_FILE = "generated_content.json"

def run_lore_content_generator():
    """Run the lore content generator and get the output."""
    try:
        result = subprocess.run(
            ["python", LORECONTENTGEN_PATH],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Parse output to get category and entry
            output = result.stdout.strip()
            category, entry = output.split("|")
            return category.strip(), entry.strip()
        else:
            print(f"Error running lore content generator: {result.stderr}")
            return None, None
    except Exception as e:
        print(f"Error running lore content generator: {str(e)}")
        return None, None

def find_latest_content_file(category, entry):
    """Find the most recent content file for the given category and entry."""
    try:
        lore_folder = Path("lore_data") / category / entry
        content_files = list(lore_folder.glob("content_*.txt"))
        if not content_files:
            return None
        return str(max(content_files, key=lambda x: x.stat().st_mtime))
    except Exception as e:
        print(f"Error finding content file: {str(e)}")
        return None

def generate_audio(content_file):
    """Generate audio from the content file."""
    try:
        result = subprocess.run(
            ["python", EDGETTSGEN_PATH, content_file],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Get the output file path from the script's output
            output = result.stdout.strip()
            for line in output.split('\n'):
                if line.startswith("Audio generated:"):
                    return line.split(": ")[1].strip()
        else:
            print(f"Error generating audio: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        return None

def create_video(content_file, audio_file):
    """Create a video from the content and audio files."""
    try:
        result = subprocess.run(
            ["python", VIDEOCREATION_PATH],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Get the output file path from the script's output
            output = result.stdout.strip()
            for line in output.split('\n'):
                if line.startswith("Video saved to:"):
                    return line.split(": ")[1].strip()
        else:
            print(f"Error creating video: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error creating video: {str(e)}")
        return None

def add_captions(video_path):
    """Add captions to the video."""
    try:
        # Get the corresponding JSON file with timing information
        json_path = str(Path(video_path).with_suffix('.json'))
        if not os.path.exists(json_path):
            print(f"Error: Timing file not found: {json_path}")
            return None
            
        output_path = add_captions_to_video(video_path, json_path)
        if output_path:
            print(f"Captions added successfully: {output_path}")
            return output_path
        return None
    except Exception as e:
        print(f"Error adding captions: {str(e)}")
        return None

def upload_to_youtube(video_path, category, entry):
    """Upload the video to YouTube."""
    try:
        # Create title and description
        title = f"Elder Scrolls Lore: {entry}"
        description = f"Exploring the lore of {entry} in The Elder Scrolls universe.\n\nCategory: {category}\n\n#ElderScrolls #TESLore #GamingLore"
        tags = ["Elder Scrolls", "TES Lore", "Gaming Lore", "Elder Scrolls Lore", "TES", "Bethesda", category, entry]
        
        # Upload video
        video_id = youtubeUploader.upload_video(
            video_path,
            title,
            description,
            tags
        )
        
        if video_id:
            # Get video URL
            video_url = f"https://youtube.com/watch?v={video_id}"
            
            # Update tracking data
            update_tracking_with_youtube(video_id, video_url)
            
            return video_id, video_url
        return None, None
    except Exception as e:
        print(f"Error uploading to YouTube: {str(e)}")
        return None, None

def update_tracking_with_youtube(video_id, video_url):
    """Update the tracking JSON with YouTube information."""
    try:
        if os.path.exists(TRACKING_FILE):
            with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        
        # Add YouTube information to the latest entry
        if data:
            latest = data[-1]
            latest['youtube'] = {
                'video_id': video_id,
                'url': video_url,
                'upload_date': datetime.datetime.now().isoformat()
            }
            
            with open(TRACKING_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error updating tracking file: {str(e)}")

def main():
    """Run the complete content generation pipeline."""
    try:
        # Step 1: Generate content
        print("Step 1: Generating content...")
        category, entry = run_lore_content_generator()
        if not category or not entry:
            print("Failed to generate content")
            return
        
        # Step 2: Find content file
        print("Step 2: Finding content file...")
        content_file = find_latest_content_file(category, entry)
        if not content_file:
            print("Failed to find content file")
            return
        
        # Step 3: Generate audio
        print("Step 3: Generating audio...")
        audio_file = generate_audio(content_file)
        if not audio_file:
            print("Failed to generate audio")
            return
        
        # Step 4: Create video
        print("Step 4: Creating video...")
        video_path = create_video(content_file, audio_file)
        if not video_path:
            print("Failed to create video")
            return
        
        # Step 5: Add captions
        print("Step 5: Adding captions...")
        captioned_video = add_captions(video_path)
        if not captioned_video:
            print("Failed to add captions")
            return
        
        # Step 6: Upload to YouTube
        print("Step 6: Uploading to YouTube...")
        video_id, video_url = upload_to_youtube(captioned_video, category, entry)
        if not video_id:
            print("Failed to upload to YouTube")
            return
        
        print(f"\nProcess completed successfully!")
        print(f"Video URL: {video_url}")
        
    except Exception as e:
        print(f"Error in main process: {str(e)}")

if __name__ == "__main__":
    main() 