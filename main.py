import requests
import asyncio
import os
from telegram import Bot

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]

def search_jobs(query):
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    params = {
        "query": query,
        "page": "1",
        "num_results": "10",
        "date_posted": "today"
    }
    r = requests.get(url, headers=headers, params=params, timeout=15)
    data = r.json()
    jobs = []
    for job in data.get("data", []):
        jobs.append({
            "title": job.get("job_title", ""),
            "company": job.get("employer_name", ""),
            "location": job.get("job_city", "") + ", " + job.get("job_country", ""),
            "link": job.get("job_apply_link", ""),
            "platform": job.get("job_publisher", "")
        })
    return jobs

async def notify(msg):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def main():
    queries = [
        "ML Engineer fresher India",
        "Data Science trainee Chennai Bengaluru",
        "SDE trainee AI India",
        "AI Engineer fresher India"
    ]

    all_jobs = []
    for q in queries:
        jobs = search_jobs(q)
        all_jobs += jobs

    if not all_jobs:
        await notify("⚠️ Bot ran — no jobs found today.")
        return

    msg = f"🔥 <b>Adhi Job Bot — {len(all_jobs)} jobs found!</b>\n\n"
    for j in all_jobs[:15]:
        msg += f"▸ <b>{j['title']}</b> @ {j['company']}\n"
        msg += f"📍 {j['location']} | {j['platform']}\n"
        if j['link']:
            msg += f"🔗 {j['link'][:70]}\n"
        msg += "\n"

    await notify(msg)
    print(f"Done. Sent {len(all_jobs)} jobs.")

if __name__ == "__main__":
    asyncio.run(main())
