import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime

# --- TAKİP EDİLECEK LİNKLER ---
SOURCES = {
    "Hepsiemlak": "https://www.hepsiemlak.com/kadikoy-kiralik",
    "Zingat": "https://www.zingat.com/kadikoy-kiralik-daire",
    "Emlakjet": "https://www.emlakjet.com/kiralik-konut/istanbul-kadikoy/"
}
DB_FILE = "data/database.json"

async def scrape_site(context, name, url):
    page = await context.new_page()
    results = []
    print(f"[{name}] Taranıyor...")
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000) # İçeriğin oturması için

        if name == "Hepsiemlak":
            items = await page.query_selector_all(".list-view-item")
            for item in items:
                title = await (await item.query_selector(".list-view-header")).inner_text()
                price = await (await item.query_selector(".list-view-price")).inner_text()
                link = await (await item.query_selector("a.img-link")).get_attribute("href")
                results.append({"id": link.split("/")[-1], "title": title.strip(), "price": price.strip(), "link": "https://www.hepsiemlak.com" + link, "source": name})

        elif name == "Zingat":
            items = await page.query_selector_all(".zl-card")
            for item in items:
                title = await (await item.query_selector(".zl-card-title")).inner_text()
                price = await (await item.query_selector(".zl-price")).inner_text()
                link = await (await item.query_selector("a.zl-card-inner")).get_attribute("href")
                results.append({"id": link.split("-")[-1], "title": title.strip(), "price": price.strip(), "link": "https://www.zingat.com" + link, "source": name})

        elif name == "Emlakjet":
            items = await page.query_selector_all("div[class*='listingItem']")
            for item in items:
                id_val = await item.get_attribute("data-id")
                title = await (await item.query_selector("h3")).inner_text()
                price = await (await item.query_selector("div[class*='price']")).inner_text()
                link = await (await item.query_selector("a")).get_attribute("href")
                results.append({"id": id_val, "title": title.strip(), "price": price.strip(), "link": "https://www.emlakjet.com" + link, "source": name})

    except Exception as e:
        print(f"[{name}] Hatası: {e}")
    finally:
        await page.close()
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        all_listings = []
        for name, url in SOURCES.items():
            site_data = await scrape_site(context, name, url)
            all_listings.extend(site_data)
        
        await browser.close()
        web_sayfasi_olustur(all_listings)

def web_sayfasi_olustur(listings):
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: database = json.load(f)
    else: database = []

    known_ids = {item["id"] for item in database}
    for item in listings:
        if item["id"] not in known_ids:
            database.insert(0, item)
    
    database = database[:100] # Son 100 ilanı tut
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(database, f, indent=4, ensure_ascii=False)

    # HTML Üretimi (Daha profesyonel kart tasarımı)
    guncelleme = datetime.now().strftime('%d/%m/%Y %H:%M')
    ilan_kartlari = ""
    for item in database:
        color = "#e67e22" if item['source'] == "Emlakjet" else "#27ae60" if item['source'] == "Hepsiemlak" else "#8e44ad"
        ilan_kartlari += f"""
        <div class="card">
            <div class="source-badge" style="background:{color}">{item['source']}</div>
            <div class="price">{item['price']}</div>
            <div class="title">{item['title']}</div>
            <a href="{item['link']}" target="_blank" class="btn">İncele</a>
        </div>"""

    html_sablon = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Profesyonel Emlak Takip Sistemi</title>
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
            .container {{ max-width: 1200px; margin: auto; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
            .card {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; position: relative; }}
            .source-badge {{ position: absolute; top: 10px; right: 10px; padding: 4px 8px; border-radius: 4px; font-size: 0.7em; font-weight: bold; }}
            .price {{ font-size: 1.6em; color: #fbbf24; font-weight: bold; margin: 15px 0 5px 0; }}
            .title {{ font-size: 0.9em; color: #94a3b8; height: 40px; overflow: hidden; margin-bottom: 15px; }}
            .btn {{ display: block; text-align: center; background: #38bdf8; color: white; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; }}
            .header {{ text-align: center; margin-bottom: 40px; border-bottom: 1px solid #334155; padding-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏢 Emlak Takip Merkezi</h1>
                <p>Kullanılan Kaynaklar: Hepsiemlak, Zingat, Emlakjet | Son Güncelleme: {guncelleme}</p>
            </div>
            <div class="grid">{ilan_kartlari if ilan_kartlari else "<p>Veriler senkronize ediliyor...</p>"}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html_sablon)

if __name__ == "__main__":
    asyncio.run(main())
