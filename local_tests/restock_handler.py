import requests

def restock(venue, sold_out_items):
    venue_id = venue["venue_id"]
    username = venue["api_username"]
    password = venue["api_password"]
    update_url = f"https://pos-integration-service.wolt.com/venues/{venue_id}/items"

    if not sold_out_items:
        print(f"[{venue_id}] ✅ No sold-out items.")
        return "No updates needed."

    # Remove duplicates
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
