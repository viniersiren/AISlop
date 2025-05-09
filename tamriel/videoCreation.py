import os
import json
import random
from datetime import datetime
from pathlib import Path
from PIL import Image
from moviepy.editor import (
    VideoFileClip, 
    ImageClip, 
    AudioFileClip, 
    CompositeVideoClip,
    concatenate_videoclips
)

# Constants
TRACKING_FILE = "generated_content.json"
OUTPUT_DIR = "generated_videos"
VIDEO_DURATION = 60  # YouTube Shorts max duration
MIN_IMAGE_DURATION = 3
MAX_IMAGE_DURATION = 5
FADE_DURATION = 1

# Image quality requirements
MIN_WIDTH = 1080
MIN_HEIGHT = 1080
TARGET_ASPECT_RATIOS = [
    (9, 16),    # Perfect vertical
    (3, 4),     # Slightly wider vertical
    (2, 3),     # Common vertical
    (1, 1),     # Square
    (4, 3),     # Landscape (less preferred)
]
ASPECT_RATIO_TOLERANCE = 0.1  # Allow 10% deviation from target ratios

def load_tracking_data():
    """Load and filter tracking data for unused entries."""
    try:
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Filter out entries that have been used
        unused_entries = {}
        for timestamp, entry in data.items():
            if not entry.get('used_for_video', False):
                unused_entries[timestamp] = entry
        
        return unused_entries
    except FileNotFoundError:
        print(f"Error: {TRACKING_FILE} not found")
        return {}
    except json.JSONDecodeError:
        print(f"Error: {TRACKING_FILE} is corrupted")
        return {}

def get_image_quality_score(image_path):
    """Calculate a quality score for the image based on dimensions and aspect ratio."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Check minimum dimensions
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                return 0
            
            # Calculate aspect ratio
            aspect_ratio = width / height
            
            # Find best matching target aspect ratio
            best_match = None
            best_score = float('inf')
            
            for target_w, target_h in TARGET_ASPECT_RATIOS:
                target_ratio = target_w / target_h
                score = abs(aspect_ratio - target_ratio)
                
                if score < best_score:
                    best_score = score
                    best_match = (target_w, target_h)
            
            # If aspect ratio is too far from any target, reject
            if best_score > ASPECT_RATIO_TOLERANCE:
                return 0
            
            # Calculate quality score
            # Higher score for:
            # 1. More vertical aspect ratios
            # 2. Higher resolution
            # 3. Closer to perfect aspect ratio match
            vertical_bonus = 1.0
            if best_match[0] < best_match[1]:  # Vertical orientation
                vertical_bonus = 1.5
            
            resolution_score = (width * height) / (MIN_WIDTH * MIN_HEIGHT)
            aspect_score = 1 - (best_score / ASPECT_RATIO_TOLERANCE)
            
            return (resolution_score * aspect_score * vertical_bonus)
            
    except Exception as e:
        print(f"Error analyzing image {image_path}: {str(e)}")
        return 0

def get_images_from_folder(folder_path):
    """Get all image files from the specified folder, sorted by quality score."""
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    images = []
    
    for file in os.listdir(folder_path):
        if file.lower().endswith(image_extensions):
            image_path = os.path.join(folder_path, file)
            quality_score = get_image_quality_score(image_path)
            if quality_score > 0:
                images.append((image_path, quality_score))
    
    # Sort by quality score, highest first
    images.sort(key=lambda x: x[1], reverse=True)
    return [img[0] for img in images]

def create_image_clip(image_path, duration):
    """Create a video clip from an image with fade effects and proper sizing."""
    try:
        # Load and analyze image
        with Image.open(image_path) as img:
            width, height = img.size
            aspect_ratio = width / height
            
            # Determine target dimensions while maintaining aspect ratio
            if aspect_ratio > 1:  # Landscape
                # Scale to fit height, center horizontally
                target_height = 1920
                target_width = int(target_height * aspect_ratio)
            else:  # Portrait or square
                # Scale to fit width, center vertically
                target_width = 1080
                target_height = int(target_width / aspect_ratio)
        
        # Create clip with proper sizing
        clip = ImageClip(image_path)
        clip = clip.resize(width=target_width, height=target_height)
        
        # Center the clip
        x_offset = (1080 - target_width) // 2
        y_offset = (1920 - target_height) // 2
        clip = clip.set_position((x_offset, y_offset))
        
        # Add fade effects
        clip = clip.crossfadein(FADE_DURATION)
        clip = clip.crossfadeout(FADE_DURATION)
        
        return clip.set_duration(duration)
    except Exception as e:
        print(f"Error creating clip from {image_path}: {str(e)}")
        return None

def create_video_from_entry(entry_data):
    """Create a video from the entry's audio and images."""
    try:
        # Get the folder path from the content file
        content_path = Path(entry_data['content_file'])
        folder_path = content_path.parent
        
        # Load audio
        audio_path = entry_data['audio_file']
        audio = AudioFileClip(audio_path)
        
        # Get images
        images = get_images_from_folder(folder_path)
        if not images:
            print(f"No suitable images found in {folder_path}")
            return None
        
        print(f"Found {len(images)} suitable images")
        
        # Create image clips
        image_clips = []
        current_duration = 0
        
        while current_duration < audio.duration and images:
            # Select image (prioritize higher quality ones)
            image_path = images[0]  # Already sorted by quality
            images.remove(image_path)
            
            # Random duration for this image
            duration = min(
                random.uniform(MIN_IMAGE_DURATION, MAX_IMAGE_DURATION),
                audio.duration - current_duration
            )
            
            # Create clip
            clip = create_image_clip(image_path, duration)
            if clip:
                image_clips.append(clip)
                current_duration += duration
        
        if not image_clips:
            print("No valid image clips created")
            return None
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(image_clips)
        
        # Add audio
        final_clip = final_clip.set_audio(audio)
        
        # Trim to audio duration
        final_clip = final_clip.subclip(0, audio.duration)
        
        return final_clip
    except Exception as e:
        print(f"Error creating video: {str(e)}")
        return None

def save_video(clip, entry_data):
    """Save the video and update tracking data."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(OUTPUT_DIR, f"lore_short_{timestamp}.mp4")
        
        # Write video file
        clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=30,
            threads=4,
            preset='ultrafast'
        )
        
        # Update tracking data
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            tracking_data = json.load(f)
        
        # Find the entry and mark it as used
        for timestamp, entry in tracking_data.items():
            if (entry['content_file'] == entry_data['content_file'] and 
                entry['audio_file'] == entry_data['audio_file']):
                entry['used_for_video'] = True
                entry['video_file'] = output_path
                break
        
        # Save updated tracking data
        with open(TRACKING_FILE, 'w', encoding='utf-8') as f:
            json.dump(tracking_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    except Exception as e:
        print(f"Error saving video: {str(e)}")
        return None

def main():
    print("Starting video creation process...")
    
    # Load tracking data
    tracking_data = load_tracking_data()
    if not tracking_data:
        print("No unused entries found")
        return
    
    # Select a random entry
    timestamp = random.choice(list(tracking_data.keys()))
    entry_data = tracking_data[timestamp]
    
    print(f"Selected entry: {entry_data['category']}/{entry_data['entry']}")
    
    # Create video
    video_clip = create_video_from_entry(entry_data)
    if not video_clip:
        print("Failed to create video")
        return
    
    # Save video and update tracking
    output_path = save_video(video_clip, entry_data)
    if not output_path:
        print("Failed to save video")
        return
    
    print(f"Video created successfully: {output_path}")
    
    # Cleanup
    video_clip.close()

if __name__ == "__main__":
    main() 