"""Searches for live job listings using the Serper.dev Google Jobs API.

Serper (https://serper.dev) exposes a simple REST endpoint that proxies
Google Jobs results, which is far cheaper and more reliable to scrape than
hitting job boards directly. Get a free API key at https://serper.dev.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

import requests

from config import (
    BACKOFF_MULTIPLIER,
    INITIAL_BACKOFF_SECONDS,
    MAX_API_RETRIES,
    SERPER_API_KEY,
)

logger = logging.getLogger("job_hunt_agents")

SERPER_JOBS_URL = "https://google.serper.dev/jobs"
RESULTS_PER_PAGE = 10  # Serper's Google Jobs endpoint returns ~10 per page.


@dataclass
class JobListing:
    """A single job listing normalised from the Serper API response."""

    title: str
    company: str
    location: str
    url: str
    description: str
    job_id: str
    via: str = ""
    raw: dict = field(default_factory=dict)

    def as_text(self) -> str:
        """Flatten the listing into a single text block for the Scout agent."""
        return (
            f"Title: {self.title}\n"
            f"Company: {self.company}\n"
            f"Location: {self.location}\n"
            f"Source: {self.via}\n"
            f"Description:\n{self.description}"
        )


def _request_with_retry(query: str, location: str, page: int) -> Optional[dict]:
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "location": location, "page": page}

    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            response = requests.post(
                SERPER_JOBS_URL, headers=headers, json=payload, timeout=30
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"Retryable status {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if attempt == MAX_API_RETRIES:
                logger.error(
                    "Serper request failed after %d attempts: %s", MAX_API_RETRIES, exc
                )
                return None
            logger.warning(
                "Serper request failed (attempt %d/%d): %s. Retrying in %.1fs...",
                attempt,
                MAX_API_RETRIES,
                exc,
                backoff,
            )
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER
    return None


def search_jobs(
    role: str, location: str, industry: str = "", max_listings: int = 100
) -> List[JobListing]:
    """Search for live job listings matching a target role.

    Args:
        role: Target job title, e.g. "Head of Data".
        location: Target location, e.g. "London".
        industry: Optional industry qualifier, e.g. "Real Estate", appended
            to the search query to narrow results.
        max_listings: Maximum number of listings to fetch.

    Returns:
        A list of JobListing objects, deduplicated by job_id/url.
    """
    if not SERPER_API_KEY:
        raise RuntimeError(
            "SERPER_API_KEY is not set. Export it as an environment variable "
            "or fill it in in config.py. Get a free key at https://serper.dev."
        )

    query = f"{role} {industry}".strip()
    logger.info(
        "Searching for jobs: query='%s' location='%s' (target=%d listings)",
        query,
        location,
        max_listings,
    )

    listings: List[JobListing] = []
    seen_ids = set()
    page = 1
    max_pages = (max_listings // RESULTS_PER_PAGE) + 2  # small buffer for dedup loss

    while len(listings) < max_listings and page <= max_pages:
        data = _request_with_retry(query, location, page)
        if not data:
            break

        jobs = data.get("jobs", [])
        if not jobs:
            logger.info("No more results returned at page %d; stopping search.", page)
            break

        for job in jobs:
            job_id = job.get("jobId") or job.get("link") or job.get("title", "")
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            listings.append(
                JobListing(
                    title=job.get("title", "Unknown Title"),
                    company=job.get("companyName", "Unknown Company"),
                    location=job.get("location", location),
                    url=job.get("link", ""),
                    description=job.get("description", ""),
                    job_id=str(job_id),
                    via=job.get("via", ""),
                    raw=job,
                )
            )
            if len(listings) >= max_listings:
                break

        page += 1

    logger.info("Fetched %d job listings.", len(listings))
    return listings[:max_listings]
