import os
import requests
import json
from dotenv import load_dotenv
import re

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
load_dotenv() 
API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
)

#print(API_KEY)
# -----------------------------------------------------------------------------
# FUNCTION
# -----------------------------------------------------------------------------

def generate_youtube_metadata(
    captions: str,
    title: str,
    metadata_dir: str,
    return_json: bool = False,
    max_existing_chars: int = 1500
):
    # 1) Gather existing metadata JSON files
    existing_text = ""
    for fn in sorted(os.listdir(metadata_dir)):
        if fn.endswith("metadata.json"):
            path = os.path.join(metadata_dir, fn)
            with open(path, "r", encoding="utf-8") as f:
                block = json.dumps(json.load(f))
            # append until we hit the limit
            if len(existing_text) + len(block) > max_existing_chars:
                # only take the head of this block
                existing_text += block[: max_existing_chars - len(existing_text)]
                break
            existing_text += block + "\n"

   # match = re.search(r'(\d+)_captions\.txt$', os.path.basename(caption_path))
    #part_number = int(match.group(1)) if match else 1
    # 2) Build prompt, including existing metadata snippet
    prompt = (
        "You are generating metadata for a YouTube Short. "
        "Ensure your output is a JSON object named SHORT_METADATA with keys: title, description, tags, category (24).\n\n"
        f"Title of source: {title}\n\n"
        "Transcribed captions:\n"
        f"{captions}\n\n"
        "Existing metadata examples (truncated):\n"
        f"{existing_text}\n\n"
        "Now generate a new SHORT_METADATA JSON object that is clearly different "
        "from the examples above."
    )

    # 3) Call Gemini
    payload = {
        "model": "gemini-2.0-flash",
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    print("PROMPT BEING SENT TO GEMINI:\n", prompt)
    print("CHAR LENGTH:", len(prompt))

    resp = requests.post(GEMINI_URL, headers=headers, json=payload)
    resp.raise_for_status()
    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    # 4) Extract the JSON block
    json_blocks = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", raw)
    if not json_blocks:
        raise ValueError("No JSON block found in Gemini response.")

    short_md = json.loads(json_blocks[0])
    SHORT_METADATA = short_md.get("SHORT_METADATA", short_md)

    #if "title" in SHORT_METADATA:
       # SHORT_METADATA["title"] = f"{SHORT_METADATA['title']} - Part {part_number}"
    return (SHORT_METADATA if return_json else short_md)

# -----------------------------------------------------------------------------
# USAGE EXAMPLE
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    caption_path = "./clips/mass_produced/51_captions.txt"
    metadata_dir = "./clips/mass_produced"
    base_title = "Fury 2014"

    # Read caption text from file
    with open(caption_path, "r", encoding="utf-8") as f:
        sample_captions = f.read()

    # Generate metadata
    short_meta = generate_youtube_metadata(
        captions=sample_captions,
        title=base_title,
        metadata_dir=metadata_dir
    )

    # Print the result
    print("SHORT_METADATA =", json.dumps(short_meta, indent=2))

