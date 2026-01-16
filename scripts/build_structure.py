import json
import os
import re
import yaml

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(BASE_DIR, "sources", "registry")
STATES_DIR = os.path.join(SOURCES_DIR, "02_states_and_uts")
DATA_DIR = BASE_DIR
LGD_DISTRICTS_PATH = os.path.join(DATA_DIR, "LGD-districts.json")
LGD_PINCODE_PATH = os.path.join(DATA_DIR, "LGD-pincode.json")

def slugify(text):
    """Converts text to a slug (lowercase, underscores)."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '_', text)
    return text

def load_json(path):
    """Loads JSON data from a file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON at {path}")
        return None

def create_yaml(path, data):
    """Writes data to a YAML file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        # Custom dumper to handle multiline strings cleanly if needed, 
        # but standard dump is usually fine for this structure.
        # We manually write the header comments as requested by user template
        
        # Identity Section
        f.write("# === IDENTITY ===\n")
        f.write(f"id: \"{data.get('id', '')}\"\n")
        f.write(f"name: \"{data.get('name', '')}\"\n")
        f.write(f"type: \"{data.get('type', '')}\"\n")
        if 'jurisdiction_level' in data:
            f.write(f"jurisdiction_level: \"{data.get('jurisdiction_level', '')}\"\n")
        f.write("\n")
        
        # Hierarchy Section
        f.write("# === HIERARCHY ===\n")
        if 'parent_district' in data:
            f.write(f"parent_district: \"{data.get('parent_district', '')}\"\n")
        if 'parent_state' in data:
            f.write(f"parent_state: \"{data.get('parent_state', '')}\"\n")
        if 'parent_union' in data:
            f.write(f"parent_union: \"{data.get('parent_union', '')}\"\n")
        if 'reporting_to' in data:
            f.write(f"reporting_to: \"{data.get('reporting_to', '')}\"\n")
        if 'capital' in data:
             f.write(f"capital: \"{data.get('capital', '')}\"\n")
        f.write("\n")
        
        # Location/Scraping Section
        if 'pincode' in data:
            f.write("# === LOCATION ===\n")
            f.write(f"pincode: {data.get('pincode', [])}\n")
            f.write("\n")
            
        if 'sections_to_watch' in data:
             f.write("# === SCRAPING CONFIG ===\n")
             f.write("url: \"\" # Placeholder\n")
             f.write("sections_to_watch:\n")
             for section in data.get('sections_to_watch', []):
                 f.write(f"  - title: \"{section['title']}\"\n")
                 f.write(f"    url: \"{section['url']}\"\n")
                 f.write(f"    urgency_default: \"{section['urgency_default']}\"\n")


def build_structure():
    print("Loading data...")
    districts_data = load_json(LGD_DISTRICTS_PATH)
    pincode_data = load_json(LGD_PINCODE_PATH)

    if not districts_data or not pincode_data:
        return

    # Process Districts
    districts_records = districts_data.get('records', [])
    
    # Organize Pincode data by State -> Local Body Name for faster lookup
    # Only keep relevant types for now or all? Let's keep all urban types.
    pincode_lookup = {}
    for record in pincode_data.get('records', []):
        state_code = str(record.get('stateCode'))
        lb_name = record.get('localBodyNameEnglish', '').lower().strip()
        
        if state_code not in pincode_lookup:
            pincode_lookup[state_code] = {}
        
        if lb_name not in pincode_lookup[state_code]:
            pincode_lookup[state_code][lb_name] = []
        
        pincode_lookup[state_code][lb_name].append(record)

    processed_states = set()

    print(f"Found {len(districts_records)} districts. Generating structure...")

    for district in districts_records:
        # State Data
        state_name = district.get('state_name_english')
        state_code = str(district.get('state_code'))
        state_slug = slugify(state_name)
        
        # District Data
        district_name = district.get('district_name_english')
        district_slug = slugify(district_name)
        
        # --- 1. Create State Directory & Meta ---
        state_dir = os.path.join(STATES_DIR, state_slug)
        if state_code not in processed_states:
            os.makedirs(state_dir, exist_ok=True)
            
            state_meta = {
                "id": f"state-{state_slug}",
                "name": state_name,
                "type": "state_government",
                "parent_union": "india",
                "capital": "" 
            }
            create_yaml(os.path.join(state_dir, "_state_meta.yaml"), state_meta)
            processed_states.add(state_code)

        # --- 2. Create District Directory & Collectorate ---
        district_dir = os.path.join(state_dir, "districts", district_slug)
        os.makedirs(district_dir, exist_ok=True)
        
        collectorate_data = {
            "id": f"dist-{state_code}-{district_slug}-coll",
            "name": f"{district_name} District Collectorate",
            "type": "district_administration",
            "jurisdiction_level": "district",
            "parent_state": state_slug,
            "reporting_to": f"Revenue Department, Govt of {state_name}",
            "sections_to_watch": [
                {"title": "Notices/Announcements", "url": "", "urgency_default": "normal"}
            ]
        }
        create_yaml(os.path.join(district_dir, "collectorate.yaml"), collectorate_data)

        # --- 3. Autofill Local Bodies (If Name Matches) ---
        # Look for a Local Body in this state with the same name as the district
        if state_code in pincode_lookup:
            normalized_d_name = district_name.lower().strip()
            
            # Try exact match first
            matches = pincode_lookup[state_code].get(normalized_d_name)
            
            if matches:
                 # Group by type (e.g. if multiple entries for same body with diff pincodes, 
                 # though typically LGD has one entry per body code. 
                 # The file has multiple entries per body code for diff pincodes? 
                 # Let's check records. Yes, same localBodyCode can appear multiple times with diff pincodes.
                 
                 unique_bodies = {}
                 for m in matches:
                     lb_code = m.get('localBodyCode')
                     if lb_code not in unique_bodies:
                         unique_bodies[lb_code] = {
                             "data": m,
                             "pincodes": []
                         }
                     unique_bodies[lb_code]["pincodes"].append(m.get('pincode'))
                
                 for lb_code, body_info in unique_bodies.items():
                     rec = body_info['data']
                     lb_type = rec.get('localBodyTypeName', 'Urban Local Body')
                     lb_type_slug = slugify(lb_type)
                     
                     # Construct filename: e.g. municipal_corporation.yaml
                     # If multiple of same type exist (rare for exact name match of district), append code
                     filename = f"{lb_type_slug}.yaml"
                     if os.path.exists(os.path.join(district_dir, filename)):
                         filename = f"{lb_type_slug}_{lb_code}.yaml"

                     ulb_data = {
                         "id": f"ulb-{state_code}-{lb_code}",
                         "name": rec.get('localBodyNameEnglish'),
                         "type": lb_type_slug,
                         "parent_district": district_slug,
                         "parent_state": state_slug,
                         "pincode": body_info['pincodes']
                     }
                     create_yaml(os.path.join(district_dir, filename), ulb_data)

    print("Structure build complete.")

if __name__ == "__main__":
    build_structure()
