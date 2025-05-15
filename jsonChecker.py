import sys
import json
import re

def extract_words_from_transcript(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Ensure that 'transcript' and 'timings' are in the right format
    transcript = data.get("transcript")
    timing = data.get("timings")
    
    if not isinstance(transcript, str) or not isinstance(timing, list):
        print(f"Error: 'transcript' or 'timings' is missing or in the wrong format in {json_file_path}")
        return

    result_words = []
    result_timing = []

    timestamps = iter(timing)  # Create an iterator for timing
    current_time = next(timestamps, None)  # Initialize current timestamp

    words = transcript.split()  # Split the transcript into words

    for word in words:

        if '<' in word:  # Word has a tag or timestamp
            word = re.sub(r'<.*?>', '', word) 
            result_words.append(word)
            result_timing.append(current_time)
        
        # Move to the next timing when a word with a timestamp is processed
        if current_time is not None and word.endswith('</c>') or True:
            current_time = next(timestamps, None)

    # Update the transcript and timings in the data
    data["transcript"] = result_words
    data["timings"] = result_timing

    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Updated transcript and timings saved to {json_file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_words_from_transcript.py <path_to_json_file>")
        sys.exit(1)

    json_file_path = sys.argv[1]
    extract_words_from_transcript(json_file_path)