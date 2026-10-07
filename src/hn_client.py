"""Hacker News Firebase REST API client for Who is Hiring extraction."""
import datetime
import html
import logging
import re
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class HackerNewsJobsClient:
    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self):
        self.client = httpx.Client(timeout=15)

    def find_latest_hiring_thread(self):
        user_url = f"{self.BASE_URL}/user/whoishiring.json"
        resp = self.client.get(user_url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        submitted = data.get("submitted", [])[:10]

        for item_id in submitted:
            item_url = f"{self.BASE_URL}/item/{item_id}.json"
            it_resp = self.client.get(item_url)
            if it_resp.status_code == 200:
                item = it_resp.json()
                title = item.get("title", "")
                if "who is hiring" in title.lower():
                    logging.info("Found hiring thread: %s (ID %s, %d comments)", title, item["id"], len(item.get("kids", [])))
                    return item
        return None

    def fetch_jobs(self, max_items=30, keyword_filter="", remote_only=False):
        thread = self.find_latest_hiring_thread()
        if not thread:
            logging.error("Could not find active Who is hiring thread.")
            return []

        kids = thread.get("kids", [])
        logging.info("Scanning %d comments from thread '%s'...", len(kids), thread.get("title"))

        jobs = []
        kw_clean = keyword_filter.strip().lower() if keyword_filter else ""

        for comment_id in kids:
            if len(jobs) >= max_items:
                break

            comment_url = f"{self.BASE_URL}/item/{comment_id}.json"
            c_resp = self.client.get(comment_url)
            if c_resp.status_code != 200:
                continue

            c_data = c_resp.json()
            if not c_data or c_data.get("deleted") or not c_data.get("text"):
                continue

            raw_text = c_data["text"]
            clean_text = html.unescape(raw_text).replace("<p>", "\n\n").replace("</p>", "")
            first_line = clean_text.split("\n")[0].strip()

            # Parse pipe-delimited title: Company | Role | Location | Remote | Tech
            parts = [p.strip() for p in first_line.split("|")]
            company = parts[0] if len(parts) > 0 else "Hiring Company"
            role = parts[1] if len(parts) > 1 else "Tech Role"
            location = parts[2] if len(parts) > 2 else "Global"
            remote_val = "Remote" if "remote" in first_line.lower() else "On-site"

            if remote_only and "remote" not in first_line.lower() and "remote" not in clean_text.lower():
                continue

            if kw_clean and kw_clean not in clean_text.lower() and kw_clean not in first_line.lower():
                continue

            # Extract email
            email_match = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', clean_text)
            contact_email = email_match[0] if email_match else ""

            # Extract URL
            url_match = re.findall(r'https?://[^\s<>"]+', clean_text)
            company_url = url_match[0].rstrip(".,;)'\"") if url_match else ""

            job_item = {
                "id": str(comment_id),
                "company": company,
                "role": role,
                "location": location,
                "remote": remote_val,
                "contactEmail": contact_email,
                "url": company_url,
                "summary": clean_text[:300] + "...",
                "fullText": clean_text,
                "hnPostUrl": f"https://news.ycombinator.com/item?id={comment_id}",
                "postedAt": datetime.datetime.fromtimestamp(c_data.get("time", 0), datetime.timezone.utc).isoformat(),
                "extractedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            jobs.append(job_item)
            logging.info("Extracted job: %s - %s (%s)", company, role, contact_email or "no email")

        logging.info("Total jobs extracted: %d", len(jobs))
        return jobs
