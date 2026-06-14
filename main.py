import requests
import asyncio
import os
from telegram import Bot
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

QUERIES = [
    "AI Engineer Tamil Nadu",
    "Machine Learning Chennai",
    "Data Scientist Tamil Nadu",
    "Data Analyst Chennai",
    "Python Developer AI Tamil Nadu",
    "Deep Learning Chennai",
    "NLP Engineer India",
    "Computer Vision fresher India",
]

def scrape_linkedin_rss(query):
    q = query.replace(" ", "%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&location=Tamil%20Nadu&f_E=1&f_TPR=r259200"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.select(".base-card")[:5]:
            title = card.select_one(".base-search-card__title")
            company = card.select_one(".base-search-card__subtitle")
            location = card.select_one(".job-search-card__location")
            link = card.select_one("a.base-card__full-link")
            if title and company:
                jobs.append({
                    "title": title.text.strip(),
                    "company": company.text.strip(),
                    "location": location.text.strip() if location else "Tamil Nadu",
                    "link": link["href"].split("?")[0] if link else ""
                })
        return jobs
    except Exception as e:
        print(f"Error scraping {query}: {e}")
        return []

async def notify(msg):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def main():
    all_jobs = []
    seen = set()

    for q in QUERIES:
        jobs = scrape_linkedin_rss(q)
        for j in jobs:
            key = f"{j['title']}-{j['company']}"
            if key not in seen:
                seen.add(key)
                all_jobs.append(j)

    if not all_jobs:
        await notify("⚠️ Bot ran — no jobs found. LinkedIn may be blocking. Will retry in 6hrs.")
        return

    msg = f"🔥 <b>Adhi Job Bot — {len(all_jobs)} Tamil Nadu AI Jobs!</b>\n\n"
    for j in all_jobs[:20]:
        msg += f"▸ <b>{j['title']}</b>\n"
        msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
        if j['link']:
            msg += f"🔗 {j['link']}\n"
        msg += "\n"

    await notify(msg)
    print(f"Done. Sent {len(all_jobs)} jobs.")

if __name__ == "__main__":
    asyncio.run(main())
