import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime

# --- AYARLAR ---
TARGET_URL = "https://www.emlakjet.com/kiralik-konut/istanbul-kadikoy/"
DB_FILE = "data/database.json"

async def scrape_emlakjet():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        print(f"[{datetime.now()}] Tarama başladı...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        listings = await page.query_selector_all("div[class*='styles_listingItem']")
        
        results = []
        for item in listings:
            try:
                id_val = await item.get_attribute("data-id")
                title_elem = await item.query_selector("h3")
                price_elem = await item.query_selector("div[class*='styles_price']")
                link_elem = await item.query_selector("a")

                if id_val and title_elem and price_elem:
                    results.append({
                        "id": id_val,
                        "title": (await title_elem.inner_text()).strip(),
                        "price": (await price_elem.inner_text()).strip(),
                        "link": "https://www.emlakjet.com" + (await link_elem.get_attribute("href"))
                    })
            except: continue

        await browser.close()
        return results

def web_sayfasi_olustur(listings):
    # Veritabanı işlemleri
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: database = json.load(f)
    else: database = []

    # Yeni gelenleri başa ekle, mükerrerleri engelle
    known_ids = {item["id"] for item in database}
    for item in listings:
        if item["id"] not in known_ids:
            database.insert(0, item)
    
    # Son 50 ilanı tut
    database = database[:50]
    with open(DB_FILE, "w") as f: json.dump(database, f, indent=4)

    # HTML Üretimi
    guncelleme = datetime.now().strftime('%d/%m/%Y %H:%M')
    ilan_kartlari = ""
    for item in database:
        ilan_kartlari += f"""
        <div class="card">
            <div class="price">{item['price']}</div>
            <div class="title">{item['title']}</div>
            <a href="{item['link']}" target="_blank" class="btn">İlana Git</a>
        </div>"""

    html_sablon = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Canlı Emlak Takip Portalı</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #f4f7f9; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: auto; }}
            h1 {{ color: #2c3e50; text-align: center; }}
            .update-time {{ text-align: center; color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 5px solid #3498db; }}
            .price {{ font-size: 1.5em; font-weight: bold; color: #e67e22; margin-bottom: 10px; }}
            .title {{ font-size: 1em; height: 50px; overflow: hidden; margin-bottom: 15px; }}
            .btn {{ display: block; text-align: center; background: #3498db; color: white; text-decoration: none; padding: 10px; border-radius: 5px; font-weight: bold; }}
            .btn:hover {{ background: #2980b9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏠 Emlak Takip Portalı</h1>
            <p class="update-time">Son Güncelleme: {guncelleme} (Her 15 dk'da bir güncellenir)</p>
            <div class="grid">{ilan_kartlari}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_sablon)

if __name__ == "__main__":
    data = asyncio.run(scrape_emlakjet())
    web_sayfasi_olustur(data)
