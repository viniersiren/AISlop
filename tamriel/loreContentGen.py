import os
import json
import random
from datetime import datetime
import google.generativeai as genai
from pathlib import Path

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Constants
LORESCRIPT_PATH = "script.txt"
LOREDATA_PATH = "lore_data"
OUTPUT_EXTENSION = ".txt"
JSON_EXTENSION = ".json"

def load_script():
    """Load the base script template."""
    try:
        with open(LORESCRIPT_PATH, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: {LORESCRIPT_PATH} not found")
        return None

def get_random_lore_entry():
    """Get a random lore entry that hasn't been processed yet."""
    # Get all category folders
    categories = [d for d in os.listdir(LOREDATA_PATH) 
                 if os.path.isdir(os.path.join(LOREDATA_PATH, d))]
    
    if not categories:
        print("No categories found in lore_data")
        return None
    
    # Try up to 10 times to find an unprocessed entry
    for _ in range(10):
        # Select random category
        category = random.choice(categories)
        category_path = os.path.join(LOREDATA_PATH, category)
        
        # Get all entry folders in category
        entries = [d for d in os.listdir(category_path) 
                  if os.path.isdir(os.path.join(category_path, d))]
        
        if not entries:
            continue
        
        # Select random entry
        entry = random.choice(entries)
        entry_path = os.path.join(category_path, entry)
        
        # Check if entry has already been processed
        if not any(f.endswith(OUTPUT_EXTENSION) for f in os.listdir(entry_path)):
            return category, entry, entry_path
    
    print("No unprocessed entries found")
    return None

def load_lore_data(entry_path):
    """Load the lore data from the entry's data.json file."""
    try:
        with open(os.path.join(entry_path, 'data.json'), 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: data.json not found in {entry_path}")
        return None

def generate_content(script, lore_data):
    """Generate content using Gemini based on the script and lore data."""
    # Extract relevant information from lore data
    title = lore_data.get('title', '')
    sections = lore_data.get('sections', [])
    
    # Format the content from sections
    content = []
    for section in sections:
        section_title = section.get('title', '')
        section_content = section.get('content', [])
        if section_title and section_content:
            content.append(f"{section_title}:\n" + "\n".join(section_content))
    
    # Create the prompt
    prompt = f"""
{script}

TITLE: {title}

CONTENT:
{chr(10).join(content)}

Please generate engaging content about this Elder Scrolls lore entry. The title is very important and should be mentioned early in the content. 
Use the provided content to create an informative and engaging narrative. Make sure to maintain the style and tone of the script template.
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating content: {str(e)}")
        return None

def save_output(entry_path, content, used_titles):
    """Save the generated content and update the used titles JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save the generated content
    output_file = os.path.join(entry_path, f"content_{timestamp}{OUTPUT_EXTENSION}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Update the used titles JSON
    json_file = os.path.join(entry_path, f"used_titles{JSON_EXTENSION}")
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            used_titles = json.load(f)
    
    used_titles[timestamp] = {
        "title": content.split('\n')[0] if content else "",
        "generated_file": f"content_{timestamp}{OUTPUT_EXTENSION}"
    }
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(used_titles, f, indent=2, ensure_ascii=False)

def main():
    # Load the script template
    script = load_script()
    if not script:
        return
    
    # Get a random unprocessed lore entry
    result = get_random_lore_entry()
    if not result:
        return
    
    category, entry, entry_path = result
    print(f"Processing {category}/{entry}")
    
    # Load the lore data
    lore_data = load_lore_data(entry_path)
    if not lore_data:
        return
    
    # Generate content
    content = generate_content(script, lore_data)
    if not content:
        return
    
    # Save the output
    save_output(entry_path, content, {})
    print(f"Content generated and saved for {category}/{entry}")

if __name__ == "__main__":
    main() 