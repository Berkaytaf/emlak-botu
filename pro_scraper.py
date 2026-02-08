import asyncio
from playwright.async_api import async_playwright
import json
import os
import requests
from datetime import datetime

# --- AYARLAR ---
TARGET_URL = "https://www.emlakjet.com/kiralik-konut/istanbul-kadikoy/"
DB_FILE = "data/database.json"

async def scrape_emlakjet():
    async with async_playwright() as p:
        # Gerçek bir insan tarayıcısı gibi davran
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        print(f"[{datetime.now()}] Tarama başladı: {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        # İlan kartlarını seç (Emlakjet güncel seçicileri)
        # Not: Site tasarımı değişirse bu seçiciler (selectors) güncellenmelidir.
        listings = await page.query_selector_all("div[class*='styles_listingItem']")
        
        results = []
        for item in listings:
            try:
                id_val = await item.get_attribute("data-id")
                # Fiyat ve başlık bilgilerini güvenli şekilde çek
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
            except Exception as e:
                continue

        await browser.close()
        return results

def notify_and_save(new_listings):
    # Veritabanı dosyasını kontrol et ve oluştur
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f: json.dump([], f)
    
    with open(DB_FILE, "r") as f:
        database = json.load(f)
    
    known_ids = [item["id"] for item in database]
    new_found_count = 0

    for item in new_listings:
        if item["id"] not in known_ids:
            # Sadece yeni ilanlar için Telegram mesajı at
            send_telegram(item)
            database.append(item)
            new_found_count += 1
    
    # Veritabanını son 200 ilanda tutarak şişmesini engelle
    with open(DB_FILE, "w") as f:
        json.dump(database[-200:], f, indent=4)
    
    print(f"İşlem tamamlandı. {new_found_count} yeni ilan Selim Abi'ye uçuruldu.")

def send_telegram(item):
    token = os.getenv("TELE_TOKEN")
    chat_id = os.getenv("TELE_CHAT_ID")
    msg = (
        f"🏠 *SELİM ABİ YENİ İLAN DÜŞTÜ!*\n\n"
        f"📍 {item['title']}\n"
        f"💰 *Fiyat:* {item['price']}\n"
        f"🔗 [İlanı Görüntüle]({item['link']})"
    )
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(scrape_emlakjet())
    notify_and_save(data)
