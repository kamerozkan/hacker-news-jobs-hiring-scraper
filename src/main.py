"""Main entrypoint for hacker-news-jobs-hiring-scraper Actor."""
import asyncio
import logging
from apify import Actor
try:
    from src.hn_client import HackerNewsJobsClient
except ImportError:
    from hn_client import HackerNewsJobsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        max_items = actor_input.get("maxItems", 30)
        keyword_filter = actor_input.get("keywordFilter", "")
        remote_only = actor_input.get("remoteOnly", False)

        Actor.log.info(f"Starting HN Jobs scraper: maxItems={max_items}, keyword='{keyword_filter}', remoteOnly={remote_only}")

        client = HackerNewsJobsClient()
        jobs = client.fetch_jobs(max_items=max_items, keyword_filter=keyword_filter, remote_only=remote_only)

        if not jobs:
            Actor.log.warning("No jobs extracted from Hacker News.")
            await Actor.set_value("OUTPUT", {"jobsExtracted": 0})
            return

        # Pay-per-event charge
        try:
            for _ in jobs:
                try:
                    await Actor.charge({"eventName": "job-extracted", "count": 1})
                except Exception:
                    pass
        except Exception:
            pass

        await Actor.push_data(jobs)
        await Actor.set_value("OUTPUT", {
            "jobsExtracted": len(jobs),
            "sampleCompany": jobs[0]["company"] if jobs else None
        })
        Actor.log.info(f"Successfully pushed {len(jobs)} jobs to dataset.")


if __name__ == "__main__":
    asyncio.run(main())
