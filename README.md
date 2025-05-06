📦 Wolt Stock Reset Automation – Documentation
Automated system to fetch menus from Wolt, detect FORCED_OUT_OF_STOCK items, and reset them to available (in_stock: true) across multiple venues.

🔧 Tech Stack
- Google Cloud Functions (2nd Gen, Python 3.12)
- Google Cloud Scheduler (runs daily at 07:00 Oslo time)
- Wolt POS API (Basic Auth)
- Cloud Logs for observability
- Configurable via venues.json

📁 Project Structure
cloud_function/
├── main.py                  # Cloud Function logic
├── requirements.txt         # Dependencies for Cloud deployment
├── venues_bakeries.json     # Bakery venues config
├── venues_groceries.json    # Grocery venues config

local_tests/
├── test_main.py             # Local entrypoint for testing
├── local_test.py            # Mock runner
├── config_loader.py         # Loads JSON configs
├── menu_fetcher.py          # Downloads menu from Wolt
├── sold_out_extractor.py    # Filters sold-out items
├── restock_handler.py       # Sends in-stock update
├── retry_utils.py           # Manages per-venue wait/retry config
├── test.json   

🧩 Features
✅ Fetches latest menu for each venue

✅ Detects sold-out items (inventory_mode == FORCED_OUT_OF_STOCK)

✅ Restocks by setting { in_stock: true }

✅ Supports both gtin and fallback to sku

✅ Can exclude specific GTINs/SKUs per venue

✅ Supports multiple config files (via ?config= param)

✅ Logs activity and errors per venue

✅ Local testing without touching Cloud Functions

✅ Temporary menu snapshot to /tmp/

🔐 Notes
Basic Auth credentials required per venue

Use "excluded_skus" or "excluded_gtins" fields in your config JSON

Items in exclusion lists are skipped during restocking

/tmp is writable in Cloud Functions; used for debug snapshots

401 errors → wrong credentials

429 errors → Wolt rate limit hit

⏰ Scheduling
Cloud Scheduler triggers the function every day at 07:00 Oslo time.
gcloud scheduler jobs create http restock-daily \
  --schedule="0 7 * * *" \
  --http-method=GET \
  --uri=https://.../reset_sold_out_items \
  --time-zone="Europe/Oslo" \
  --location=europe-west1

🔍 Logs
To view logs:
gcloud functions logs read reset_sold_out_items \
  --region=europe-west1 --limit=50

Sample log output:
[6668459d0ccf81b89dfb3447] 🛒 Sold-out items: 6
[6668459d0ccf81b89dfb3447] 🔁 Restocking items: 7035620053429, 4198, 4015, ...
[6668459d0ccf81b89dfb3447] ✅ Items successfully marked as in stock

🚀 Manual Trigger
You can manually test the function:
curl https://europe-west1-<project-id>.cloudfunctions.net/reset_sold_out_items
Or locally (for testing, not cloud):
python3 main.py


✨ Maintainer
Author: Ivo Tonkovski
Feel free to expand this project or clone it for other APIs. You've now got a robust, cloud-native, auto-restocking Wolt integration 👏