import sys
import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime
import random

# --- DİNAMİK HEDEF AYARI ---
# GitHub Actions'tan gelen (veya manuel verilen) şehir ve ilçe bilgilerini al
# Örnek kullanım: python pro_scraper.py istanbul kadikoy
TARGET_CITY = sys.argv[1].lower() if len(sys.argv) > 1 else "istanbul"
TARGET_DISTRICT = sys.argv[2].lower() if len(sys.argv) > 2 else "kadikoy"

# URL'leri Selim Abi'nin seçimine göre otomatik oluştur
SOURCES = {
    "Hepsiemlak": f"https://www.hepsiemlak.com/{TARGET_DISTRICT}-kiralik",
    "Zingat": f"https://www.zingat.com/{TARGET_DISTRICT}-kiralik-daire",
    "Emlakjet": f"https://www.emlakjet.com/kiralik-konut/{TARGET_CITY}-{TARGET_DISTRICT}/"
}

DB_FILE = "data/database.json"

async def auto_scroll(page):
    """Lazy-load ilanları tetiklemek için insan gibi aşağı kaydırır."""
    await page.evaluate("""
        async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 150;
                let timer = setInterval(() => {
                    let scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if(totalHeight >= scrollHeight){
                        clearInterval(timer);
                        resolve();
                    }
                }, 150);
            });
        }
    """)

async def scrape_site(context, name, url):
    page = await context.new_page()
    # "Ben robot değilim" koruması
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    results = []
    print(f"[{name}] HEDEF: {TARGET_CITY}/{TARGET_DISTRICT} -> {url}")
    
    try:
        # İnsan gibi rastgele bekleme
        await asyncio.sleep(random.uniform(3, 7))
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Sayfayı yavaşça kaydırarak gizli ilanları aç
        await page.wait_for_timeout(2000)
        await auto_scroll(page)
        await page.wait_for_timeout(4000)

        if name == "Hepsiemlak":
            items = await page.query_selector_all(".list-view-item, article")
            for item in items:
                try:
                    title_elem = await item.query_selector(".list-view-header, h3")
                    price_elem = await item.query_selector(".list-view-price, .price")
                    link_elem = await item.query_selector("a")
                    if title_elem and price_elem:
                        title = (await title_elem.inner_text()).strip()
                        price = (await price_elem.inner_text()).strip()
                        link = await link_elem.get_attribute("href")
                        results.append({
                            "id": str(hash(title + price)),
                            "title": title, "price": price,
                            "link": "https://www.hepsiemlak.com" + link if link.startswith("/") else link,
                            "source": name, "location": f"{TARGET_CITY}/{TARGET_DISTRICT}"
                        })
                except: continue

        elif name == "Zingat":
            items = await page.query_selector_all(".zl-card, .listing-item")
            for item in items:
                try:
                    title_elem = await item.query_selector(".zl-card-title, h3")
                    price_elem = await item.query_selector(".zl-price, .price")
                    link_elem = await item.query_selector("a")
                    if title_elem and price_elem:
                        title = (await title_elem.inner_text()).strip()
                        price = (await price_elem.inner_text()).strip()
                        link = await link_elem.get_attribute("href")
                        results.append({
                            "id": str(hash(title + price)),
                            "title": title, "price": price,
                            "link": "https://www.zingat.com" + link if link.startswith("/") else link,
                            "source": name, "location": f"{TARGET_CITY}/{TARGET_DISTRICT}"
                        })
                except: continue

        elif name == "Emlakjet":
            items = await page.query_selector_all("div[class*='listingItem']")
            for item in items:
                try:
                    title_elem = await item.query_selector("h3")
                    price_elem = await item.query_selector("div[class*='price']")
                    link_elem = await item.query_selector("a")
                    if title_elem and price_elem:
                        title = (await title_elem.inner_text()).strip()
                        price = (await price_elem.inner_text()).strip()
                        link = await link_elem.get_attribute("href")
                        results.append({
                            "id": str(hash(title + price)),
                            "title": title, "price": price,
                            "link": "https://www.emlakjet.com" + link if link.startswith("/") else link,
                            "source": name, "location": f"{TARGET_CITY}/{TARGET_DISTRICT}"
                        })
                except: continue

    except Exception as e:
        print(f"[{name}] HATA: {e}")
    finally:
        await page.close()
    
    print(f"--- [{name}] {len(results)} ilan bulundu. ---")
    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )

        all_listings = []
        for name, url in SOURCES.items():
            site_data = await scrape_site(context, name, url)
            all_listings.extend(site_data)
            await asyncio.sleep(random.uniform(5, 10))
        
        await browser.close()
        
        if all_listings:
            web_sayfasi_olustur(all_listings)
        else:
            print("Veri çekilemediği için sayfa güncellenmedi.")

def web_sayfasi_olustur(listings):
    os.makedirs("data", exist_ok=True)
    database = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f: database = json.load(f)
        except: database = []

    # Yeni ilanları başa ekle
    existing_ids = {item["id"] for item in database}
    new_items = [i for i in listings if i["id"] not in existing_ids]
    
    # Yeni olanlar en üste, toplam 100 ilan
    database = new_items + database
    database = database[:100]

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(database, f, indent=4, ensure_ascii=False)

    guncelleme = datetime.now().strftime('%d/%m/%Y %H:%M')
    ilan_kartlari = "".join([f"""
        <div class="card">
            <div class="source-badge">{item['source']}</div>
            <div class="location-badge">{item.get('location', 'Bilinmiyor')}</div>
            <div class="price">{item['price']}</div>
            <div class="title">{item['title']}</div>
            <a href="{item['link']}" target="_blank" class="btn">İncele</a>
        </div>""" for item in database])

    html_content = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Selim Abi Emlak Takip</title>
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
            .container {{ max-width: 1200px; margin: auto; }}
            .header {{ text-align: center; border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 30px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
            .card {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; position: relative; }}
            .source-badge {{ position: absolute; top: 10px; right: 10px; background: #38bdf8; padding: 4px 8px; border-radius: 4px; font-size: 0.7em; font-weight: bold; }}
            .location-badge {{ position: absolute; top: 10px; left: 10px; background: #475569; padding: 4px 8px; border-radius: 4px; font-size: 0.6em; }}
            .price {{ font-size: 1.5em; color: #fbbf24; font-weight: bold; margin-top: 20px; }}
            .title {{ font-size: 0.9em; color: #94a3b8; height: 45px; overflow: hidden; margin: 10px 0; }}
            .btn {{ display: block; text-align: center; background: #38bdf8; color: white; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏠 Selim Abi'nin Emlak Portalı</h1>
                <p>Şu An İzlenen: <b>{TARGET_CITY.upper()} / {TARGET_DISTRICT.upper()}</b></p>
                <p>Son Güncelleme: {guncelleme}</p>
            </div>
            <div class="grid">{ilan_kartlari if database else '<h3>İlan bulunamadı...</h3>'}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__":
    asyncio.run(main())
