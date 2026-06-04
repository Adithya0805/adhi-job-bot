import requests
import telegram
import time, os

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

def notify(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

def search_indeed(query, location="India"):
    url = "https://indeed-indeed.p.rapidapi.com/apisearch"
    headers = {
        "X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"],
        "X-RapidAPI-Host": "indeed-indeed.p.rapidapi.com"
    }
    params = {
        "q": query,
        "l": location,
        "sort": "date",
        "limit": "10",
        "fromage": "1"
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    data = r.json()
    jobs = []
    for job in data.get("results", []):
        jobs.append({
            "title": job.get("jobtitle", ""),
            "company": job.get("company", ""),
            "location": job.get("formattedLocation", ""),
            "link": job.get("url", ""),
            "date": job.get("date", "")
        })
    return jobs

def main():
    queries = [
        "ML Engineer fresher",
        "Data Science trainee",
        "SDE trainee AI",
        "AI Engineer fresher"
    ]

    all_jobs = []
    for q in queries:
        jobs = search_indeed(q, "India")
        all_jobs += jobs
        time.sleep(1)

    if not all_jobs:
        notify("⚠️ Bot ran — no new jobs found today.")
        return

    msg = f"🔥 <b>Adhi Job Bot — {len(all_jobs)} jobs found!</b>\n\n"
    for j in all_jobs[:15]:
        msg += f"▸ <b>{j['title']}</b> @ {j['company']}\n"
        msg += f"📍 {j['location']}\n"
        if j['link']:
            msg += f"🔗 {j['link'][:60]}\n"
        msg += "\n"

    notify(msg)
    print(f"Done. Sent {len(all_jobs)} jobs.")

if __name__ == "__main__":
    main()
