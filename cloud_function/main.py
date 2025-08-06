import requests
import json
import time
import os
from datetime import datetime
import flask

DEFAULT_WAIT = 30
RETRY_CONFIG_PATH = "/tmp/retry_delay_config.json"

# ─────────────────────────────────────────────────────
# Load venue config from JSON
def load_venues(config_name="venues.json"):
    try:
        with open(config_name, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load venues config '{config_name}': {e}")
        return []

# ─────────────────────────────────────────────────────
# Retry delay utils
def load_retry_config():
    if os.path.exists(RETRY_CONFIG_PATH):
        try:
            with open(RETRY_CONFIG_PATH, "r") as f:
                return json.load(f)
        except:
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

# ─────────────────────────────────────────────────────
# Fetch Wolt menu and save to /tmp
def fetch_menu(venue):
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

    for attempt in range(8):
        menu_response = requests.get(resource_url)
        if menu_response.status_code != 200:
            print(f"[{venue_id}] ❌ Failed to fetch menu (attempt {attempt + 1}): {menu_response.status_code}")
            time.sleep(6)
            continue

        try:
            menu_data = menu_response.json()
        except Exception as e:
            print(f"[{venue_id}] ❌ Failed to parse menu JSON (attempt {attempt + 1}): {e}")
            time.sleep(6)
            continue

        if menu_data.get("status") == "READY":
            menu_data["venue_id"] = venue_id  # ✅ Inject venue ID here

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
        time.sleep(6)

    print(f"[{venue_id}] ❌ Menu still not READY after 8 attempts.")
    increase_wait_time(venue_id)
    return None

# ─────────────────────────────────────────────────────
# Extract sold-out items, respecting exclusion/inclusion lists
def get_sold_out_items(menu_data, excluded_gtins=None, excluded_skus=None,
                       included_gtins=None, included_skus=None):
    items = menu_data.get("menu", {}).get("items", [])
    sold_out = []
    venue_id = menu_data.get("venue_id", "unknown")

    excluded_gtins = set(excluded_gtins or [])
    excluded_skus = set(excluded_skus or [])
    included_gtins = set(included_gtins or [])
    included_skus = set(included_skus or [])

    for item in items:
        inventory_mode = item.get("inventory_mode")
        product = item.get("product", {})
        gtin = product.get("gtin")
        sku = product.get("sku")

        if inventory_mode != "FORCED_OUT_OF_STOCK":
            continue

        if gtin in excluded_gtins or sku in excluded_skus:
            continue

        if included_gtins or included_skus:
            if gtin and gtin not in included_gtins and not (sku and sku in included_skus):
                continue
            if sku and sku not in included_skus and not (gtin and gtin in included_gtins):
                continue

        if gtin:
            sold_out.append({"type": "gtin", "id": gtin})
        elif sku:
            sold_out.append({"type": "sku", "id": sku})
        else:
            print(f"[{venue_id}] ⚠️ Skipping item with no GTIN/SKU")

    return sold_out

# ─────────────────────────────────────────────────────
# Update items to in-stock via Wolt API
def restock(venue, sold_out_items):
    venue_id = venue["venue_id"]
    username = venue["api_username"]
    password = venue["api_password"]
    update_url = f"https://pos-integration-service.wolt.com/venues/{venue_id}/items"

    if not sold_out_items:
        print(f"[{venue_id}] ✅ No sold-out items.")
        return "No updates needed."

    seen = set()
    unique_items = []
    for item in sold_out_items:
        key = (item["type"], item["id"])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    payload = {
        "data": [
            {item["type"]: item["id"], "in_stock": True}
            for item in unique_items
        ]
    }

    item_list = ", ".join([item["id"] for item in unique_items])
    print(f"[{venue_id}] 🔁 Restocking {len(unique_items)} items: {item_list}")

    response = requests.patch(
        update_url,
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        json=payload
    )

    if response.status_code == 202:
        print(f"[{venue_id}] ✅ Items successfully marked as in stock.")
        return f"Restocked {len(unique_items)} items."
    else:
        print(f"[{venue_id}] ❌ Failed to update: {response.status_code} - {response.text}")
        return f"Update failed: {response.status_code}"

# ─────────────────────────────────────────────────────
# MAIN Cloud Function entry
def reset_sold_out_items(request):
    config_name = request.args.get("config", "venues.json")
    venues = load_venues(config_name)
    if not venues:
        return f"No venues found in config: {config_name}", 500

    results = {}

    for venue in venues:
        venue_id = venue.get("venue_id", "unknown")
        excluded_gtins = venue.get("excluded_gtins", [])
        excluded_skus = venue.get("excluded_skus", [])
        included_gtins = venue.get("included_gtins", [])
        included_skus = venue.get("included_skus", [])

        menu = fetch_menu(venue)
        if not menu:
            results[venue_id] = "❌ Failed to fetch menu"
            continue

        sold_out_items = get_sold_out_items(
            menu,
            excluded_gtins=excluded_gtins,
            excluded_skus=excluded_skus,
            included_gtins=included_gtins,
            included_skus=included_skus
        )
        print(f"[{venue_id}] 🛒 Sold-out items: {len(sold_out_items)}")

        result = restock(venue, sold_out_items)
        results[venue_id] = result

        time.sleep(10)

    return json.dumps(results, indent=2), 200
