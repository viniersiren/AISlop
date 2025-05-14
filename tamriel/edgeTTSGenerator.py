import edge_tts
import asyncio
import sys
import os
import json
from pathlib import Path

# Available voices can be found at: https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support?tabs=tts
VOICE = "en-US-GuyNeural"  # Authoritative male voice
# Voice settings for a more grand, natural sound
VOICE_SETTINGS = {
    "rate": "-10%",     # Slightly slower for more gravitas
    "volume": "+20%",   # Louder for more presence
    "pitch": "+2Hz"     # Slightly higher pitch for more natural intonation
}
OUTPUT_DIR = "generated_audio"

async def generate_audio(text_file: str, output_file: str = None) -> str:
    """
    Generate audio from a text file using Edge TTS with word timing.
    
    Args:
        text_file (str): Path to the text file containing the script
        output_file (str, optional): Path for the output audio file. If not provided,
                                   will use the text file name with .mp3 extension
    Returns:
        str: Path to the generated audio file
    """
    try:
        # Read the text file
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        
        if not text:
            print("Error: Text file is empty")
            return None
        
        # If no output file specified, use text file name with .mp3
        if not output_file:
            output_file = str(Path(text_file).with_suffix('.mp3'))
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        
        print(f"Generating audio for: {text_file}")
        print(f"Using voice: {VOICE}")
        print(f"Voice settings: {VOICE_SETTINGS}")
        print(f"Output will be saved to: {output_file}")
        
        # Initialize the TTS with custom settings
        communicate = edge_tts.Communicate(
            text, 
            VOICE,
            rate=VOICE_SETTINGS["rate"],
            volume=VOICE_SETTINGS["volume"],
            pitch=VOICE_SETTINGS["pitch"]
        )
        
        # Get word timing information
        words = []
        timings = []
        
        # Stream the audio and collect word boundaries
        async for message in communicate.stream():
            if message["type"] == "WordBoundary":
                words.append(message["text"])
                timings.append((message["offset"] / 10000000, message["duration"] / 10000000))
        
        # Generate the audio
        print(f"Generating audio for {len(words)} words...")
        await communicate.save(output_file)
        
        # Save timing information
        timing_file = str(Path(output_file).with_suffix('.json'))
        with open(timing_file, 'w', encoding='utf-8') as f:
            json.dump({
                'words': words,
                'timings': timings
            }, f, indent=2, ensure_ascii=False)
        
        print("Audio generation completed successfully!")
        print(f"Timing information saved: {timing_file}")
        
        return output_file
    except FileNotFoundError:
        print(f"Error: Text file '{text_file}' not found")
        return None
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python edgeTTSGenerator.py <text_file> [output_file]")
        print("Example: python edgeTTSGenerator.py script.txt output.mp3")
        sys.exit(1)
    
    text_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run the async function
    asyncio.run(generate_audio(text_file, output_file))

if __name__ == "__main__":
    main() 