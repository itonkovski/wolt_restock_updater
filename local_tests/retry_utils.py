import os
import json

RETRY_CONFIG_PATH = "/tmp/retry_delay_config.json"
DEFAULT_WAIT = 15

def load_retry_config():
    if os.path.exists(RETRY_CONFIG_PATH):
        try:
            with open(RETRY_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_retry_config(config):
    try:
        with open(RETRY_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save retry config: {e}")

def get_wait_time(venue_id):
    config = load_retry_config()
    return config.get(venue_id, DEFAULT_WAIT)

def increase_wait_time(venue_id):
    config = load_retry_config()
    config[venue_id] = config.get(venue_id, DEFAULT_WAIT) + 5
    save_retry_config(config)

def reset_wait_time(venue_id):
    config = load_retry_config()
    if venue_id in config:
        del config[venue_id]
        save_retry_config(config)
