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
def generate_youtube_metadata(captions: str, title: str, returnJson: bool = False):
    prompt = (
        f"Generate one JSON object, SHORT_METADATA, including a title, description, tags and category(24), it will be a youtube short"
        f"for a YouTube short \n"
        f"Ttle of show/movie: {title}\n"
f"""Captions:
r o d n e y   i   r i d e   k n e w   i   w a s   w r i t i n g   y o u   k n o w   h e   c a m e   f r o m   d o e s   y o u r   f o c u s   b o t h   t h e   d o g   a n d   l e t's   g e t   o u t   o f   y o u r   b u l l e t s   w h a t   t h e   f u c k   o k a y   t h a n k s   r e a l l y   w h y   y ' a l l   s n o o p i n g   o n   m e   w h i l e   y o u   u n d e r s t a n d   t h a t   t h e   v i c t i m s   w e r e   g o n n a   t e l l   y o u   r i g h t   n o w   d o n ' t   f u c k i n g   c a l l   m e   d i n a   f u c k i n g   a n   a t l a n t a   f a l c o n   d o   l a m a   w a s   k i n d   o f   a n   o m i n o u s   a n d   y o u   w a n t   t o   t a l k   m e x i c a n   j o i n   a n o t h e r   t a n k   m e x i c a n   t a n k   t h i s   a m e r i c a n   t a n k   w e   t a l k   i n t o   f u c k i n g   n i g g l i n g   c r a p"""
    )
    payload = {
        "model": "gemini-2.0-flash",
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(GEMINI_URL, headers=headers, json=payload)
    resp.raise_for_status()
    result = resp.json()
    
    raw = result["candidates"][0]["content"]["parts"][0]["text"]
    # 3) Find all ```json ... ``` blocks
    json_blocks = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", raw)
    if len(json_blocks) < 1:
        raise ValueError("Did not find one JSON blocks in the response.")
    
    short_md = json.loads(json_blocks[0])
    
    # 5) Extract the inner SHORT_METADATA dict
    SHORT_METADATA = short_md.get("SHORT_METADATA", short_md)
    
    # 6) Since VIDEO_METADATA is the same, we only return SHORT_METADATA
    return SHORT_METADATA

# -----------------------------------------------------------------------------
# USAGE EXAMPLE
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    sample_captions = "Nandor tries to bribe the stockbroker with real blood..."
    base_title = "Fury 2014"
    short_meta = generate_youtube_metadata(sample_captions, base_title)
    print("SHORT_METADATA =", json.dumps(short_meta, indent=2))
