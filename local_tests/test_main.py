import time
import json
from config_loader import load_venues
from retry_utils import get_wait_time, reset_wait_time, increase_wait_time
from menu_fetcher import fetch_menu
from sold_out_extractor import get_sold_out_items, get_menu_items
from restock_handler import restock


class MockRequest:
    def __init__(self, config_name):
        self.args = {"config": config_name}


def reset_sold_out_items(request):
    config_name = request.args.get("config", "test.json")
    venues = load_venues(config_name)
    if not venues:
        return f"No venues found in config: {config_name}", 500

    results = {}

    for venue in venues:
        venue_id = venue.get("venue_id", "unknown")
        excluded_gtins = set(venue.get("excluded_gtins", []))
        excluded_skus = set(venue.get("excluded_skus", []))
        included_gtins = set(venue.get("included_gtins", []))
        included_skus = set(venue.get("included_skus", []))

        menu = fetch_menu(venue, get_wait_time, increase_wait_time, reset_wait_time)
        if not menu:
            results[venue_id] = "❌ Failed to fetch menu"
            continue

        if included_skus or included_gtins:
            menu_items = get_menu_items(menu)
            sold_out_items = []
            for item in menu_items:
                product = item.get("product", {})
                sku = product.get("sku")
                gtin = product.get("gtin")
                inventory_mode = item.get("inventory_mode")
                availability = item.get("availability")

                if sku in included_skus and (availability == "SOLD_OUT" or inventory_mode == "FORCED_OUT_OF_STOCK"):
                    sold_out_items.append({"type": "sku", "id": sku})
                elif gtin in included_gtins and (availability == "SOLD_OUT" or inventory_mode == "FORCED_OUT_OF_STOCK"):
                    sold_out_items.append({"type": "gtin", "id": gtin})
        else:
            sold_out_items = get_sold_out_items(menu, excluded_gtins, excluded_skus)

        if sold_out_items:
            print(f"[{venue_id}] 🔁 Restocking {len(sold_out_items)} items: {', '.join(item['id'] for item in sold_out_items)}")
            result = restock(venue, sold_out_items)
        else:
            print(f"[{venue_id}] ✅ No sold-out items.")
            result = "No updates needed."

        results[venue_id] = result
        time.sleep(5)

    return json.dumps(results, indent=2), 200


if __name__ == "__main__":
    mock_request = MockRequest("test.json")
    response, status_code = reset_sold_out_items(mock_request)
    print("Status Code:", status_code)
    print("Response:\n", response)
