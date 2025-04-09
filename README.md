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
├── main.py                # Core logic & entrypoint
├── venues.json            # List of venues with credentials
├── requirements.txt       # Python dependencies (just 'requests')

🧩 Features
- Fetches latest menu for each venue
- Detects sold-out items (inventory_mode == FORCED_OUT_OF_STOCK)
- Updates those items to { in_stock: true }
- Supports both gtin and fallback to sku
- Saves temporary snapshot (optional, /tmp)
- Logs activity per venue
- Works with multiple venues in parallel

🔐 Notes
- Credentials use Basic Auth (username + password/token)
- Only /tmp is writable in Cloud Functions (menu snapshots are not persisted)
- Errors like 401 usually mean wrong credentials or Wolt API access issues
- 429 means you've hit Wolt's rate limit (try again later)

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