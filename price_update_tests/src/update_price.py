import requests
import csv

# ---- FUNCTION TO LOAD CSV ----
def load_price_updates_from_csv(file_path):
    items = []
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                gtin = row["gtin"]
                price_eur = float(row["price"])
                price_cents = int(price_eur * 100)

                items.append({
                    "gtin": gtin,
                    "price": price_cents
                })
            except (KeyError, ValueError) as e:
                print(f"⚠️ Skipping row due to error: {e}")
    return items

# ---- CONFIG ----
VENUE_ID = "6668459d0ccf81b89dfb3447"
API_USERNAME = "joker_test"
API_PASSWORD = "94136f4988ffe98d9fa9f22648eb2955745f0ff53ee82e04be14a2fbbd1c5d57"
API_URL = f"https://pos-integration-service.wolt.com/venues/{VENUE_ID}/items"

# ---- BUILD PAYLOAD FROM CSV ----
payload = {
    "data": load_price_updates_from_csv("price_updates.csv")
}

# ---- SEND TO WOLT API ----
def update_prices():
    try:
        print(f"Updating {len(payload['data'])} items...")
        response = requests.patch(
            API_URL,
            auth=(API_USERNAME, API_PASSWORD),
            headers={"Content-Type": "application/json"},
            json=payload
        )

        if response.status_code == 202:
            print("✅ Price update successful!")
        else:
            print(f"❌ Update failed: {response.status_code} - {response.text}")

    except requests.RequestException as e:
        print(f"🚨 Request error: {e}")

if __name__ == "__main__":
    update_prices()
