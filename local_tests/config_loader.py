# local_tests/config_loader.py

import json

def load_venues(config_filename):
    """
    Loads the venue configuration from the specified JSON file.
    """
    try:
        with open(config_filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load venues config '{config_filename}': {e}")
        return []
