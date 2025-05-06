# local_tests/menu_fetcher.py

import os
import time
import json
import requests
from datetime import datetime
from retry_utils import get_wait_time, increase_wait_time, reset_wait_time

def fetch_menu(venue, get_wait_time, increase_wait_time, reset_wait_time):
    venue_id = venue["venue_id"]
    username = venue["api_username"]
    password = venue["api_password"]
    menu_url = f"https://pos-integration-service.wolt.com/v2/venues/{venue_id}/menu"

    print(f"[{venue_id}] 📥 Fetching menu...")
    response = requests.get(menu_url, auth=(username, password))
    if response.status_code != 202:
        print(f"[{venue_id}] ❌ Initial request failed: {response.status_code}")
        increase_wait_time(venue_id)
        return None

    resource_url = response.json().get("resource_url")
    if not resource_url:
        print(f"[{venue_id}] ❌ No resource URL.")
        increase_wait_time(venue_id)
        return None

    wait_time = get_wait_time(venue_id)
    print(f"[{venue_id}] ⏳ Waiting {wait_time} seconds...")
    time.sleep(wait_time)

    for attempt in range(3):
        menu_response = requests.get(resource_url)
        if menu_response.status_code != 200:
            print(f"[{venue_id}] ❌ Failed to fetch menu (attempt {attempt + 1}): {menu_response.status_code}")
            time.sleep(3)
            continue

        try:
            menu_data = menu_response.json()
        except Exception as e:
            print(f"[{venue_id}] ❌ Failed to parse menu JSON (attempt {attempt + 1}): {e}")
            time.sleep(3)
            continue

        if menu_data.get("status") == "READY":
            menu_data["venue_id"] = venue_id 
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_dir = "/tmp/menu_snapshots"
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"menu_{venue_id}_{timestamp}.json")
            with open(filepath, "w") as f:
                json.dump(menu_data, f, indent=2)
            print(f"[{venue_id}] 💾 Menu saved to {filepath}")
            reset_wait_time(venue_id)
            return menu_data

        print(f"[{venue_id}] ⏳ Menu not READY yet (attempt {attempt + 1})...")
        time.sleep(3)

    print(f"[{venue_id}] ❌ Menu still not READY after 3 attempts.")
    increase_wait_time(venue_id)
    return None
