import requests
import csv
import json
import datetime
from pathlib import Path

# ---- LOAD CONFIG ----
CONFIG_PATH = Path("config/venues.json")
DATA_DIR = Path("data")

with open(CONFIG_PATH) as f:
    config = json.load(f)

venues = config["venues"]

# ---- GET CSV FILE FOR TODAY ----
def get_csv_path_for_today():
    today_str = datetime.date.today().isoformat()
    file_path = DATA_DIR / f"price_updates_{today_str}.csv"
    if not file_path.exists():
        print(f"⚠️ No CSV found for today ({today_str}): {file_path}")
        return None
    return file_path

# ---- FUNCTION TO LOAD PRICE UPDATES ----
def load_price_updates_from_csv(file_path):
    items = []
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                gtin = row["gtin"].strip()
                price_eur = float(row["price"])
                price_cents = int(price_eur * 100)
                items.append({"gtin": gtin, "price": price_cents})
            except (KeyError, ValueError) as e:
                print(f"⚠️ Skipping row due to error: {e}")
    return items

# ---- FUNCTION TO UPDATE A SINGLE VENUE ----
def update_prices_for_venue(venue, items):
    api_url = f"https://pos-integration-service.wolt.com/venues/{venue['id']}/items"
    payload = {"data": items}

    try:
        print(f"\n📡 Sending update to {venue['name']} (ID: {venue['id']})...")
        response = requests.patch(
            api_url,
            auth=(venue["username"], venue["password"]),
            headers={"Content-Type": "application/json"},
            json=payload
        )

        if response.status_code == 202:
            gtins = [item['gtin'] for item in items]
            print(f"✅ Updated {len(items)} items for {venue['name']} (ID: {venue['id']}): {', '.join(gtins)}")

        else:
            print(f"❌ Failed for {venue['name']}: {response.status_code} - {response.text}")

    except requests.RequestException as e:
        print(f"🚨 Request error for {venue['name']}: {e}")

# ---- MAIN ----
def main():
    csv_path = get_csv_path_for_today()
    if not csv_path:
        return

    items = load_price_updates_from_csv(csv_path)
    if not items:
        print("⚠️ No valid items found in CSV. Exiting.")
        return

    for venue in venues:
        update_prices_for_venue(venue, items)

if __name__ == "__main__":
    main()
