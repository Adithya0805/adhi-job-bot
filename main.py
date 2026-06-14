import requests
import asyncio
import os
from telegram import Bot
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# PRIMARY — Tamil Nadu Startups & Companies
TAMIL_NADU_QUERIES = [
    "AI Engineer fresher Chennai startups",
    "Machine Learning Engineer entry level Chennai",
    "Generative AI Developer fresher Chennai",
    "Data Scientist junior Coimbatore",
    "Python AI Developer entry level Chennai",
    "LLM Engineer fresher Tamil Nadu",
    "NLP Engineer entry level Chennai",
    "Data Analyst AI fresher Madurai",
    "MLOps Engineer trainee Chennai",
    "Computer Vision Engineer fresher Chennai",
    "AI Research Engineer entry level Tamil Nadu",
    "Deep Learning Developer fresher Coimbatore",
]

# SECONDARY — Remote India (profile match only)
REMOTE_INDIA_QUERIES = [
    "Generative AI Engineer remote India fresher",
    "LLM Developer remote India entry level",
    "Machine Learning Engineer remote India 0-2 years",
    "Python AI Developer remote India fresher",
    "RAG Engineer remote India entry level",
    "FastAPI AI Developer remote India fresher",
    "LangChain Developer remote India junior",
    "Data Scientist remote India fresher",
]

# Adhi's exact skill stack
SKILL_KEYWORDS = [
    "python", "langchain", "langgraph", "fastapi", "llm",
    "generative ai", "rag", "machine learning", "deep learning",
    "nlp", "aws", "bedrock", "pinecone", "vector database",
    "transformer", "huggingface", "openai", "gemini", "nextjs",
    "tensorflow", "pytorch", "scikit-learn", "data science",
    "mlops", "ai engineer", "large language model", "chatbot",
    "computer vision", "entry level", "fresher", "trainee"
]

# Block these completely
BLOCK_KEYWORDS = [
    "senior", "lead", "manager", "director", "head of",
    "principal", "architect", "5+ years", "7+ years", "10+ years",
    "vp ", "chief", "unpaid", "usa", "uk", "canada", "australia",
    "germany", "singapore", "dubai", "uae", "europe", "us only",
    "united states", "united kingdom", "onsite usa", "onsite uk"
]

def score_job(title, company, location):
    text = (title + " " + company + " " + location).lower()

    # Hard block
    for block in BLOCK_KEYWORDS:
        if block in text:
            return -1, []

    # Score match
    score = 0
    matched = []
    for skill in SKILL_KEYWORDS:
        if skill in text:
            score += 1
            matched.append(skill)

    # Bonus score for Tamil Nadu
    tn_cities = ["chennai", "coimbatore", "madurai", "trichy", "salem",
                 "erode", "vellore", "tamil nadu", "tamilnadu"]
    for city in tn_cities:
        if city in text:
            score += 2
            break

    # Bonus for fresher/entry level
    if any(w in text for w in ["fresher", "entry level", "trainee", "0-2", "junior"]):
        score += 1

    return score, matched

def scrape_linkedin(query, location_filter=""):
    q = query.replace(" ", "%20")
    # f_E=1,2 = Internship + Entry level | f_TPR=r259200 = last 3 days
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&f_E=1,2&f_TPR=r259200"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.select(".base-card")[:5]:
            title    = card.select_one(".base-search-card__title")
            company  = card.select_one(".base-search-card__subtitle")
            location = card.select_one(".job-search-card__location")
            link     = card.select_one("a.base-card__full-link")

            if not (title and company and link):
                continue

            loc_text = location.text.strip() if location else ""

            # For Tamil Nadu queries — block non-India locations
            if location_filter == "india":
                foreign = ["usa", "uk", "canada", "australia", "germany",
                          "singapore", "dubai", "europe", "united states",
                          "united kingdom", "remote (us", "remote (uk"]
                if any(f in loc_text.lower() for f in foreign):
                    continue

            clean_link = link["href"].split("?")[0]
            if "linkedin.com/jobs" not in clean_link:
                continue

            jobs.append({
                "title":    title.text.strip(),
                "company":  company.text.strip(),
                "location": loc_text,
                "link":     clean_link
            })
        return jobs
    except Exception as e:
        print(f"Scrape error: {query} — {e}")
        return []

async def notify(msg):
    bot = Bot(token=BOT_TOKEN)
    if len(msg) > 4000:
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="HTML")
            await asyncio.sleep(1)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def main():
    all_jobs = []
    seen = set()

    # Scrape Tamil Nadu first
    print("Scraping Tamil Nadu jobs...")
    for q in TAMIL_NADU_QUERIES:
        for j in scrape_linkedin(q, location_filter="india"):
            key = f"{j['title'].lower()}-{j['company'].lower()}"
            if key not in seen:
                seen.add(key)
                score, matched = score_job(j["title"], j["company"], j["location"])
                if score == -1:
                    continue
                j["score"]   = score
                j["matched"] = matched
                j["type"]    = "tn"
                all_jobs.append(j)

    # Scrape Remote India
    print("Scraping Remote India jobs...")
    for q in REMOTE_INDIA_QUERIES:
        for j in scrape_linkedin(q, location_filter="india"):
            key = f"{j['title'].lower()}-{j['company'].lower()}"
            if key not in seen:
                seen.add(key)
                score, matched = score_job(j["title"], j["company"], j["location"])
                if score == -1:
                    continue
                j["score"]   = score
                j["matched"] = matched
                j["type"]    = "remote"
                all_jobs.append(j)

    if not all_jobs:
        await notify("⚠️ Bot ran — no matching jobs found. Retrying in 6hrs.")
        return

    # Sort best match first
    all_jobs.sort(key=lambda x: x["score"], reverse=True)

    tn_jobs     = [j for j in all_jobs if j["type"] == "tn"]
    remote_jobs = [j for j in all_jobs if j["type"] == "remote"]
    high_match  = [j for j in all_jobs if j["score"] >= 3]

    # Header report
    msg  = f"🔥 <b>Adhi Job Bot — Daily Report</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 Total Jobs: <b>{len(all_jobs)}</b>\n"
    msg += f"🏙 Tamil Nadu: <b>{len(tn_jobs)}</b>\n"
    msg += f"🌐 Remote India: <b>{len(remote_jobs)}</b>\n"
    msg += f"⭐ High Match (3+): <b>{len(high_match)}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    # Tamil Nadu jobs first
    if tn_jobs:
        msg += f"🏙 <b>TAMIL NADU JOBS ({len(tn_jobs)})</b>\n\n"
        for j in tn_jobs[:12]:
            stars = "⭐" * min(j["score"], 5)
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
            msg += f"🎯 {stars} Match: {j['score']}/7"
            if j["matched"]:
                msg += f" | {', '.join(j['matched'][:2])}"
            msg += f"\n🔗 {j['link']}\n\n"

    # Remote India jobs
    if remote_jobs:
        msg += f"🌐 <b>REMOTE INDIA JOBS ({len(remote_jobs)})</b>\n\n"
        for j in remote_jobs[:8]:
            stars = "⭐" * min(j["score"], 5)
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
            msg += f"🎯 {stars} Match: {j['score']}/7\n"
            msg += f"🔗 {j['link']}\n\n"

    await notify(msg)
    print(f"Done. TN: {len(tn_jobs)} | Remote: {len(remote_jobs)} | High match: {len(high_match)}")

if __name__ == "__main__":
    asyncio.run(main())
