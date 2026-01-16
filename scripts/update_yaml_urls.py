import json
import os
import yaml
import re

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_DIR = os.path.join(BASE_DIR, "sources", "registry", "02_states_and_uts")
URLS_FILE = os.path.join(BASE_DIR, "data", "igod_urls.json")

def normalize(text):
    """Normalize string for fuzzy matching (lowercase, remove 'district', 'collectorate', non-alphanumeric)."""
    if not text: return ""
    text = text.lower()
    text = text.replace("district", "").replace("collectorate", "")
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def save_yaml_content(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def update_yaml_url(path, url):
    """Updates the 'url: ""' line in the YAML file text string directly to preserve comments."""
    content = load_yaml(path)
    
    # Simple string replacement for safely updating the placeholder
    # Search for url: "" # Placeholder or just url: ""
    
    # We look for the blank url pattern
    new_line = f'url: "{url}"'
    
    # Pattern: url: "" (with optional whitespace and optional # comment)
    pattern = r'url:\s*""(\s*#.*)?'
    
    if re.search(pattern, content):
        content = re.sub(pattern, new_line, content, count=1)
        save_yaml_content(path, content)
        return True
    return False

def main():
    if not os.path.exists(URLS_FILE):
        print("URL data file not found. Run fetch_urls.py first.")
        return

    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        url_map = json.load(f)
        
    # Pre-process url map for easier matching
    normalized_map = {normalize(k): v for k, v in url_map.items()}
    
    updated_count = 0
    failed_districts = []
    
    print("Scanning directory structure...")
    
    for root, dirs, files in os.walk(REGISTRY_DIR):
        for file in files:
            if file == "collectorate.yaml":
                path = os.path.join(root, file)
                
                # Extract district name from the file content or path
                # Let's read the YAML 'name' field
                content = load_yaml(path)
                match = re.search(r'name:\s*"([^"]+)"', content)
                if match:
                    original_name = match.group(1)
                    norm_name = normalize(original_name)
                    
                    found_url = None
                    
                    # 1. Exact Normal Match
                    if norm_name in normalized_map:
                        found_url = normalized_map[norm_name]
                    
                    # 2. Fallback: Check if IGOD name is substring of YAML name or vice versa
                    if not found_url:
                        for k, v in normalized_map.items():
                            if k in norm_name or norm_name in k:
                                # safety check: don't match short strings like "s" to "sh"
                                if len(k) > 3 and len(norm_name) > 3:
                                    found_url = v
                                    break
                    
                    if found_url:
                        if update_yaml_url(path, found_url):
                             updated_count += 1
                             # print(f"Updated {original_name} -> {found_url}")
                    else:
                        failed_districts.append(original_name)
    
    print("-" * 30)
    print(f"Total Authenticated: {updated_count}")
    print(f"Failed to Match: {len(failed_districts)}")
    print("-" * 30)
    
    if failed_districts:
        print("\nDistricts with no match found in IGOD:")
        for name in failed_districts: 
             print(f" - {name}")

if __name__ == "__main__":
    main()
