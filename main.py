import requests
import asyncio
import os
import json
import hashlib
from google import genai
from google.genai import types
from telegram import Bot
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Validate environment variables
BOT_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID     = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_KEY  = os.environ.get("GEMINI_API_KEY")
SEEN_FILE   = "seen_jobs.json"

if not BOT_TOKEN or not CHAT_ID or not GEMINI_KEY:
    logger.error("Missing required environment variables. Ensure TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, and GEMINI_API_KEY are set.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_KEY)

# ── ADHI'S PROFILE ─────────────────────────────────────────
ADHI_PROFILE = """
Name: Adithya (Adhi)
Degree: B.Tech AI & Data Science — 2025 Fresher
Core Skills: Python, LangChain, LangGraph, FastAPI, AWS Bedrock,
             Pinecone RAG, Next.js, Supabase, Gemini API
Flagship Projects:
  - MediGuard V2: Multi-agent clinical AI (LangGraph + AWS Bedrock + Pinecone + FastAPI)
  - TownRise AI: Real estate intelligence platform (Next.js + Supabase + Gemini API)
Target Roles: AI Engineer, ML Engineer, GenAI Developer,
              Data Scientist, Python Developer, LLM Engineer
Experience Target: 0-2 years / Fresher / Entry Level / Trainee
Location Priority: Tamil Nadu > Bangalore > Hyderabad > Remote India
Company Preference: AI-first startups and product companies
                    over IT service body shops
"""

# ── CONSOLIDATED SEARCH QUERIES (Reduced from 37 to 6 to prevent LinkedIn blocks) ──
TAMIL_NADU_QUERIES = [
    '("Generative AI" OR "LLM" OR "AI Developer" OR "Machine Learning" OR "NLP" OR "Computer Vision" OR "MLOps" OR "AI") AND (fresher OR "entry level" OR trainee) AND (Chennai OR "Tamil Nadu")',
    '(Python OR FastAPI OR Django OR Backend) AND (fresher OR "entry level" OR trainee OR junior) AND (Chennai OR "Tamil Nadu")',
    '("Software Engineer" OR "Data Scientist" OR "Data Analyst" OR "Data Engineer" OR "Developer" OR IT OR "Trainee" OR "Associate") AND (fresher OR "entry level" OR trainee OR junior) AND (Chennai OR "Tamil Nadu" OR Coimbatore OR Madurai)'
]

METRO_QUERIES = [
    '("Generative AI" OR "LLM" OR "Machine Learning" OR "AI Engineer" OR "Python AI" OR "Data Scientist" OR "GenAI") AND (fresher OR "entry level" OR junior OR trainee) AND (Bangalore OR Bengaluru)',
    '("Generative AI" OR "LLM" OR "Machine Learning" OR "AI Engineer" OR "Data Scientist" OR "GenAI") AND (fresher OR "entry level" OR junior OR trainee) AND Hyderabad'
]

REMOTE_QUERIES = [
    '("AI Engineer" OR "Machine Learning" OR "Python" OR "Generative AI" OR "LLM" OR "Data Scientist" OR "Backend") AND (fresher OR "entry level" OR junior OR trainee) AND remote AND India'
]

# ── HARD BLOCKS ────────────────────────────────────────────
BLOCK_WORDS = [
    "senior", "lead", "manager", "director", "head of", "principal",
    "architect", "5+ years", "7+ years", "10+ years", "vp ", "chief",
    "unpaid", "usa", "uk", "canada", "australia", "germany", "singapore",
    "dubai", "uae", "europe", "us only", "united states", "united kingdom",
    "remote (us", "remote (uk", "malaysia", "philippines", "worldwide"
]

INDIA_CITIES = [
    "india", "chennai", "bangalore", "bengaluru", "hyderabad",
    "mumbai", "pune", "delhi", "coimbatore", "madurai",
    "tamil nadu", "karnataka", "telangana", "maharashtra",
    "remote india", "pan india"
]

FOREIGN_WORDS = [
    "usa", "uk", "canada", "australia", "germany", "singapore",
    "dubai", "europe", "united states", "united kingdom",
    "remote (us", "remote (uk", "worldwide", "global remote"
]

# ── TIER 1 PRODUCT COMPANIES ───────────────────────────────
TIER1_COMPANIES = [
    "zoho", "freshworks", "chargebee", "postman", "browserstack",
    "razorpay", "zerodha", "groww", "cred", "meesho", "phonepe",
    "swiggy", "zomato", "ola", "byju", "unacademy", "vedantu",
    "innovaccer", "darwinbox", "kissflow", "leadsquared", "madras",
    "slintel", "netapp", "paypal", "amazon", "google", "microsoft",
    "atlassian", "freshdesk", "agnikul", "pixxel", "sigmoid",
    "saama", "mu sigma", "tredence", "latentview"
]

def load_seen():
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
    except Exception as e:
        logger.error(f"Error loading seen files: {e}")
    return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logger.error(f"Error saving seen files: {e}")

def make_key(title, company):
    return hashlib.md5(f"{title.lower()}-{company.lower()}".encode()).hexdigest()

def is_blocked(title, company, location):
    text = f"{title} {company} {location}".lower()
    return any(b in text for b in BLOCK_WORDS)

def is_foreign_remote(location):
    loc = location.lower()
    return any(f in loc for f in FOREIGN_WORDS)

def get_company_tier(company):
    name = company.lower()
    if any(t in name for t in TIER1_COMPANIES):
        return 1
    if any(s in name for s in ["tech", "ai", "labs", "studio", "works",
                                 "soft", "solutions", "systems", "data"]):
        return 2
    return 3

def get_location_score(location):
    loc = location.lower()
    if any(c in loc for c in ["chennai", "coimbatore", "madurai", "tamil nadu",
                                "vellore", "trichy", "salem", "erode"]):
        return 10
    if "remote" in loc and any(c in loc for c in INDIA_CITIES):
        return 9
    if any(c in loc for c in ["bangalore", "bengaluru"]):
        return 8
    if "hyderabad" in loc:
        return 7
    return 5

async def analyze_with_gemini(title, company, location):
    """Use Gemini to intelligently score each job against Adhi's profile"""
    prompt = f"""
You are a senior AI career advisor analyzing a job opportunity for this candidate:

{ADHI_PROFILE}

Job Details:
- Title: {title}
- Company: {company}
- Location: {location}

Analyze this job and return ONLY a JSON object with no extra text:
{{
  "skill_match": <0-10>,
  "role_growth": <0-10>,
  "accessibility": <0-10>,
  "company_quality": <0-10>,
  "is_relevant": <true/false>,
  "reason": "<one sharp sentence why this fits or doesnt fit Adhi>"
}}

CRITICAL RULES:
- Never recommend internships paying under ₹15,000/month (if it seems to be an unpaid or low-paying internship, set "is_relevant" to false).
- Never recommend senior roles or roles requiring 5+ years of experience (set "is_relevant" to false).
- Ensure "is_relevant" is true ONLY if the job is a good fit for a fresher AI/ML Engineer or Python Developer in India.
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return {
            "skill_match": 5,
            "role_growth": 5,
            "accessibility": 5,
            "company_quality": 5,
            "is_relevant": True,
            "reason": "Could not analyze — manual review needed"
        }

def calculate_final_score(gemini_result, location, company):
    loc_score     = get_location_score(location)
    tier          = get_company_tier(company)
    tier_score    = {1: 10, 2: 7, 3: 3}.get(tier, 5)

    skill_match = gemini_result.get("skill_match", 5)
    role_growth = gemini_result.get("role_growth", 5)
    accessibility = gemini_result.get("accessibility", 5)

    final = (
        skill_match    * 0.35 +
        tier_score                       * 0.25 +
        role_growth    * 0.20 +
        loc_score                        * 0.10 +
        accessibility  * 0.10
    )
    return round(final, 1)

def scrape_linkedin(query, mode="tn"):
    q = urllib.parse.quote(query)
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&f_E=1,2&f_TPR=r604800"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        cards = soup.select(".base-card, .base-search-card")
        for card in cards[:15]:  # Process up to 15 cards per query since queries are broader now
            title    = card.select_one(".base-search-card__title")
            company  = card.select_one(".base-search-card__subtitle, .base-search-card__subtitle a")
            location = card.select_one(".job-search-card__location")
            link     = card.select_one("a.base-card__full-link, a.base-search-card__full-link")

            if not (title and company and link):
                continue

            loc_text = location.text.strip() if location else ""

            # Remote mode — confirm India, block foreign
            if mode == "remote":
                if is_foreign_remote(loc_text):
                    continue
                if not any(c in loc_text.lower() for c in INDIA_CITIES):
                    continue

            clean_link = link["href"].split("?")[0]
            if "linkedin.com/jobs" not in clean_link:
                continue

            jobs.append({
                "title":    title.text.strip(),
                "company":  company.text.strip(),
                "location": loc_text,
                "link":     clean_link,
                "mode":     mode
            })
        return jobs
    except Exception as e:
        logger.error(f"Scrape error [{query}]: {e}")
        return []

async def send_telegram_message(bot, msg):
    if len(msg) > 4000:
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="HTML", disable_web_page_preview=True)
            await asyncio.sleep(1)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML", disable_web_page_preview=True)

async def send_reminder(bot, top_jobs):
    logger.info("Waiting 2 hours before sending application reminders...")
    await asyncio.sleep(7200)
    
    msg  = "⏰ <b>Apply Reminder — Adhi!</b>\n\n"
    msg += "These are waiting for your application:\n\n"
    for i, j in enumerate(top_jobs, 1):
        msg += f"{i}. <b>{j['title']}</b> @ {j['company']}\n"
        msg += f"   🎯 Score: {j['final_score']}/10\n"
        msg += f"   🔗 {j['link']}\n\n"
    msg += "⚡ <b>Apply NOW. First applicants win.</b>\n"
    msg += "Your MediGuard V2 + TownRise AI = strong portfolio. Use it."
    
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML", disable_web_page_preview=True)
        logger.info("Sent 2-hour reminder.")
    except Exception as e:
        logger.error(f"Error sending reminder: {e}")

async def main():
    seen = load_seen()
    raw_jobs = []
    new_seen = set()

    # ── Collect all raw jobs ───────────────────────────────
    logger.info("Scraping Tamil Nadu...")
    for q in TAMIL_NADU_QUERIES:
        for j in scrape_linkedin(q, mode="tn"):
            key = make_key(j["title"], j["company"])
            if key not in seen and key not in new_seen:
                if not is_blocked(j["title"], j["company"], j["location"]):
                    new_seen.add(key)
                    raw_jobs.append(j)

    logger.info("Scraping Bangalore + Hyderabad...")
    for q in METRO_QUERIES:
        for j in scrape_linkedin(q, mode="metro"):
            key = make_key(j["title"], j["company"])
            if key not in seen and key not in new_seen:
                if not is_blocked(j["title"], j["company"], j["location"]):
                    new_seen.add(key)
                    raw_jobs.append(j)

    logger.info("Scraping Remote India...")
    for q in REMOTE_QUERIES:
        for j in scrape_linkedin(q, mode="remote"):
            key = make_key(j["title"], j["company"])
            if key not in seen and key not in new_seen:
                if not is_blocked(j["title"], j["company"], j["location"]):
                    new_seen.add(key)
                    raw_jobs.append(j)

    async with Bot(token=BOT_TOKEN) as bot:
        if not raw_jobs:
            logger.info("No new raw jobs found since last run.")
            await bot.send_message(
                chat_id=CHAT_ID,
                text="✅ Bot ran — no new jobs since last check. Next alert in 3 days.",
                parse_mode="HTML"
            )
            return

        logger.info(f"Found {len(raw_jobs)} new raw jobs. Running Gemini analysis...")
        
        # Limit Gemini analysis to top 30 raw jobs to avoid hitting rate limits or taking too long
        raw_jobs = raw_jobs[:30]

        # ── Gemini AI Analysis ─────────────────────────────────
        analyzed_jobs = []
        
        # IT Body Shops to filter
        IT_BODY_SHOPS = ["tcs", "tata consultancy", "wipro", "infosys", "cognizant", "accenture", "capgemini", "hcl", "tech mahindra", "l&t", "ltimindtree"]

        for j in raw_jobs:
            analysis = await analyze_with_gemini(j["title"], j["company"], j["location"])
            
            # Layer 2 check: Check if relevancy flag is false
            if not analysis.get("is_relevant", False):
                continue
            
            skill_match = analysis.get("skill_match", 0)
            
            # Rule: Never show IT body shop roles unless skill match above 8
            company_lower = j["company"].lower()
            is_body_shop = any(shop in company_lower for shop in IT_BODY_SHOPS)
            if is_body_shop and skill_match <= 8:
                continue

            j["analysis"]    = analysis
            j["final_score"] = calculate_final_score(analysis, j["location"], j["company"])
            j["tier"]        = get_company_tier(j["company"])
            
            # Rule: Only pass jobs scoring above 5.0 to Telegram
            if j["final_score"] < 5.0:
                continue
                
            analyzed_jobs.append(j)
            
            # Sleep 4.2s to comply with Gemini API free tier rate limit (15 RPM)
            await asyncio.sleep(4.2)

        # If no jobs match our criteria
        if not analyzed_jobs:
            logger.info("No jobs passed the AI relevancy and scoring filters.")
            save_seen(seen.union(new_seen))
            await bot.send_message(
                chat_id=CHAT_ID,
                text="✅ Bot ran — scanned jobs but none met the criteria score (> 5.0). Next alert in 3 days.",
                parse_mode="HTML"
            )
            return

        # ── Save seen + sort ───────────────────────────────────
        save_seen(seen.union(new_seen))
        analyzed_jobs.sort(key=lambda x: x["final_score"], reverse=True)

        # ── Top 10 only ────────────────────────────────────────
        top_jobs    = analyzed_jobs[:10]
        tn_jobs     = [j for j in analyzed_jobs if j["mode"] == "tn"]
        metro_jobs  = [j for j in analyzed_jobs if j["mode"] == "metro"]
        remote_jobs = [j for j in analyzed_jobs if j["mode"] == "remote"]

        tier_badge = {1: "🏆 TIER 1", 2: "⭐ TIER 2", 3: "🔹 TIER 3"}
        mode_label = {"tn": "🏙 Tamil Nadu", "metro": "🌆 Metro", "remote": "🌐 Remote India"}

        now = datetime.now().strftime("%d %b %Y")
        msg  = f"🤖 <b>Adhi AI Job Bot — {now}</b>\n"
        msg += f"<i>Gemini-analyzed. Curated for your profile.</i>\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🔍 Scanned: <b>{len(raw_jobs)}</b> raw jobs\n"
        msg += f"🤖 AI Filtered: <b>{len(analyzed_jobs)}</b> relevant\n"
        msg += f"📤 Sending Top: <b>{len(top_jobs)}</b> curated picks\n"
        msg += f"🏙 TN: <b>{len(tn_jobs)}</b> | 🌆 Metro: <b>{len(metro_jobs)}</b> | 🌐 Remote: <b>{len(remote_jobs)}</b>\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"🏆 <b>YOUR TOP 10 MATCHES</b>\n\n"

        for i, j in enumerate(top_jobs, 1):
            badge = tier_badge.get(j["tier"], "🔹")
            loc   = mode_label.get(j["mode"], "📍")
            score = j["final_score"]
            reason = j["analysis"]["reason"]

            # Score bar
            filled = int(score)
            bar = "█" * filled + "░" * (10 - filled)

            msg += f"<b>{i}. {j['title']}</b>\n"
            msg += f"🏢 {j['company']} {badge}\n"
            msg += f"{loc} | 📍 {j['location']}\n"
            msg += f"🎯 [{bar}] {score}/10\n"
            msg += f"💡 {reason}\n"
            msg += f"🔗 {j['link']}\n\n"

        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"⚡ <b>Apply top 5 within 24hrs.</b>\n"
        msg += f"Next alert in <b>3 days</b> with fresh jobs."

        await send_telegram_message(bot, msg)

        # Trigger delayed reminder if we sent jobs
        if top_jobs:
            # We block here synchronously to keep the GitHub Actions runner alive for the reminder.
            await send_reminder(bot, top_jobs[:5])

        logger.info(f"Done. Sent {len(top_jobs)} AI-curated jobs.")

if __name__ == "__main__":
    asyncio.run(main())
