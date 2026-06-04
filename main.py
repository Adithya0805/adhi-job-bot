import json
import logging
import os
import sys
from datetime import datetime
from hashlib import sha256

import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import TelegramError

SEARCH_ROLES = [
    "ML Engineer",
    "Data Science Trainee",
    "SDE Trainee",
    "AI Engineer",
]
SEARCH_LOCATIONS = [
    "Chennai",
    "Bengaluru",
    "Remote India",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}
SEEN_JOBS_FILE = "seen_jobs.json"
MAX_MESSAGES = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_seen_jobs():
    if not os.path.exists(SEEN_JOBS_FILE):
        return set()

    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, IOError):
        logger.warning("Could not read %s, starting with empty seen jobs.", SEEN_JOBS_FILE)
        return set()

    return set(data) if isinstance(data, list) else set()


def save_seen_jobs(seen_ids):
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as handle:
            json.dump(sorted(seen_ids), handle, indent=2)
    except IOError as exc:
        logger.error("Failed to write seen jobs: %s", exc)


def job_id(job):
    unique = job.get("link") or f"{job.get('title')}|{job.get('company')}|{job.get('location')}"
    return sha256(unique.encode("utf-8")).hexdigest()


def send_telegram_message(bot_token, chat_id, text):
    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.")

    bot = Bot(token=bot_token)
    try:
        bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info("Sent Telegram message.")
    except TelegramError as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        raise


def format_job_message(job):
    return (
        f"🔥 {job['title']} @ {job['company']} [{job['platform']}]\n"
        f"📍 {job['location']} | 🗓 {job['date_posted']}\n"
        f"🔗 {job['link']}"
    )


def safe_text(element):
    return element.get_text(strip=True) if element else "N/A"


def parse_naukri_job(card):
    title_el = card.select_one("a.title")
    company_el = card.select_one("a.subTitle")
    location_el = card.select_one("li.location span") or card.select_one("span.location")
    date_el = card.select_one("span.date")
    link = title_el["href"] if title_el and title_el.has_attr("href") else None

    return {
        "title": safe_text(title_el),
        "company": safe_text(company_el),
        "location": safe_text(location_el),
        "date_posted": safe_text(date_el) or "Recent",
        "link": link or "https://www.naukri.com",
        "platform": "Naukri",
    }


def scrape_naukri(role, location):
    query = requests.utils.quote(role)
    place = requests.utils.quote(location)
    url = (
        f"https://www.naukri.com/{query}-jobs-in-{place}"
        f"?k={query}&l={place}&experience=0-1"
    )
    logger.info("Scraping Naukri: %s", url)

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:
        logger.error("Naukri scrape failed: %s", exc)
        raise

    cards = soup.select("article.jobTuple, div.jobTuple")
    jobs = []
    for card in cards:
        job = parse_naukri_job(card)
        if job["title"] and job["company"]:
            jobs.append(job)

    logger.info("Found %s Naukri jobs for %s / %s.", len(jobs), role, location)
    return jobs


def parse_indeed_job(card):
    title_el = card.select_one("h2.jobTitle span") or card.select_one("a.tapItem")
    company_el = card.select_one("span.companyName")
    location_el = card.select_one("div.companyLocation")
    date_el = card.select_one("span.date") or card.select_one("span.posted")
    link_el = card.select_one("a.jcs-JobTitle, a.tapItem, a[href*='/rc/clk']")
    link = None
    if link_el and link_el.has_attr("href"):
        href = link_el["href"]
        if href.startswith("/"):
            link = f"https://in.indeed.com{href}"
        else:
            link = href

    return {
        "title": safe_text(title_el),
        "company": safe_text(company_el),
        "location": safe_text(location_el),
        "date_posted": safe_text(date_el) or "Recent",
        "link": link or "https://in.indeed.com",
        "platform": "Indeed",
    }


def scrape_indeed(role, location):
    query = requests.utils.quote(role)
    place = requests.utils.quote(location)
    url = (
        f"https://in.indeed.com/jobs?q={query}&l={place}"
        f"&explvl=entry_level&fromage=7"
    )
    logger.info("Scraping Indeed: %s", url)

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:
        logger.error("Indeed scrape failed: %s", exc)
        raise

    cards = soup.select("div.job_seen_beacon, a.tapItem, div.slider_container")
    jobs = []
    seen_links = set()
    for card in cards:
        job = parse_indeed_job(card)
        if job["link"] in seen_links:
            continue
        seen_links.add(job["link"])
        if job["title"] and job["company"]:
            jobs.append(job)

    logger.info("Found %s Indeed jobs for %s / %s.", len(jobs), role, location)
    return jobs


def scrape_linkedin_easy_apply():
    enabled = os.environ.get("LINKEDIN_ENABLED", "false").lower() == "true"
    if not enabled:
        logger.info("LinkedIn scraping is disabled. Set LINKEDIN_ENABLED=true to enable it.")
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright is not installed. Skipping LinkedIn scraping.")
        return []

    logger.info("Starting optional LinkedIn easy apply scrape.")
    query = "+OR+".join([requests.utils.quote(role) for role in SEARCH_ROLES])
    search_url = (
        "https://www.linkedin.com/jobs/search/?keywords="
        f"{query}&location=India&f_E=1&f_TP=1"
    )
    jobs = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(search_url, timeout=60000)
        page.wait_for_timeout(5000)

        cards = page.query_selector_all(".jobs-search-results__list-item")
        for card in cards[:25]:
            easy = card.query_selector(".job-card-container__easy-apply")
            if not easy:
                continue

            title_el = card.query_selector("h3")
            company_el = card.query_selector("h4")
            location_el = card.query_selector("span.job-search-card__location")
            link_el = card.query_selector("a")
            link = link_el.get_attribute("href") if link_el else None

            if link and link.startswith("/"):
                link = f"https://www.linkedin.com{link}"

            jobs.append({
                "title": title_el.inner_text().strip() if title_el else "N/A",
                "company": company_el.inner_text().strip() if company_el else "N/A",
                "location": location_el.inner_text().strip() if location_el else "N/A",
                "date_posted": "Recent",
                "link": link or "https://www.linkedin.com/jobs/",
                "platform": "LinkedIn Easy Apply",
            })

        browser.close()

    logger.info("Found %s LinkedIn Easy Apply jobs.", len(jobs))
    return jobs


def run():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")
        raise SystemExit(1)

    seen_jobs = load_seen_jobs()
    new_jobs = []

    try:
        for role in SEARCH_ROLES:
            for location in SEARCH_LOCATIONS:
                new_jobs.extend(scrape_naukri(role, location))
                new_jobs.extend(scrape_indeed(role, location))
    except Exception as exc:
        warning = f"⚠️ Job scraper failed: {exc}"
        logger.exception("Crawling failed.")
        try:
            send_telegram_message(bot_token, chat_id, warning)
        except Exception:
            pass
        return

    new_jobs.extend(scrape_linkedin_easy_apply())

    unique_jobs = {}
    for job in new_jobs:
        jid = job_id(job)
        if jid not in unique_jobs:
            unique_jobs[jid] = job

    new_jobs = [job for jid, job in unique_jobs.items() if jid not in seen_jobs]
    if not new_jobs:
        logger.info("No new jobs to send.")
        return

    if len(new_jobs) > MAX_MESSAGES:
        new_jobs = sorted(new_jobs, key=lambda item: item.get("date_posted", ""), reverse=True)[:MAX_MESSAGES]

    for job in new_jobs:
        message = format_job_message(job)
        try:
            send_telegram_message(bot_token, chat_id, message)
        except Exception:
            logger.error("Stopping job notifications due to Telegram error.")
            break
        seen_jobs.add(job_id(job))

    save_seen_jobs(seen_jobs)


if __name__ == "__main__":
    run()
