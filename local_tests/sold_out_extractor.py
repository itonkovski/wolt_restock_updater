def get_sold_out_items(menu_data, excluded_gtins, excluded_skus):
    items = menu_data.get("menu", {}).get("items", [])
    venue_id = menu_data.get("venue_id", "unknown")

    skipped_gtins = []
    skipped_skus = []
    sold_out = []

    for item in items:
        inventory_mode = item.get("inventory_mode")
        product = item.get("product", {})
        gtin = product.get("gtin")
        sku = product.get("sku")
        item_id = item.get("id")

        if inventory_mode == "FORCED_OUT_OF_STOCK":
            if gtin and gtin in excluded_gtins:
                skipped_gtins.append(gtin)
                continue
            if sku and sku in excluded_skus:
                skipped_skus.append(sku)
                continue

            if gtin:
                sold_out.append({"type": "gtin", "id": gtin})
            elif sku:
                sold_out.append({"type": "sku", "id": sku})
            elif item_id:
                print(f"[{venue_id}] ⚠️ Skipping item with no GTIN/SKU — only using ID: {item_id}")
            else:
                print(f"[{venue_id}] ⚠️ Skipping item with no identifier")

    if skipped_gtins:
        print(f"[{venue_id}] ⏭️ Skipping GTINs: {', '.join(skipped_gtins)}")
    if skipped_skus:
        print(f"[{venue_id}] ⏭️ Skipping SKUs: {', '.join(skipped_skus)}")

    return sold_out
