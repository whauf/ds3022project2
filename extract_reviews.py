
import os
import json
import time
import httpx

from pathlib import Path
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timezone

REPOS = [
    "numpy/numpy",
    "networkx/networkx",
    "statsmodels/statsmodels"
]

BASE_URL = "https://api.github.com"
PER_PAGE = 100

# Start with a small test before the full extraction.
MAX_PRS_PER_REPO = None

def fetch(client, url, params):
    for attempt in range(5):
        response = client.get(url, params=params)

        if response.status_code in (403, 429):
            remaining = int(
                response.headers.get("X-RateLimit-Remaining", 1)
            )

            if remaining == 0:
                reset = int(
                    response.headers.get("X-RateLimit-Reset", 0)
                )
                wait = max(1, reset - time.time() + 5)
            else:
                wait = min(60 * (attempt + 1), 300)

            print(f"Rate limited. Waiting {wait:.0f}s.")
            time.sleep(wait)
            continue

        if response.status_code >= 500:
            time.sleep(2 ** attempt)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError(f"Request failed: {url}")


def main():
    token = os.environ["GITHUB_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    with httpx.Client(headers=headers, timeout=60) as client:
        for repo in REPOS:
            pr_folder = (
                Path("data/raw")
                / repo.replace("/", "__")
                / "pulls"
            )

            review_folder = (
                Path("data/raw")
                / repo.replace("/", "__")
                / "reviews"
            )
            review_folder.mkdir(parents=True, exist_ok=True)

            processed = 0

            for pr_file in sorted(pr_folder.glob("page_*.json")):
                saved = json.loads(pr_file.read_text())

                for pr in saved["data"]:
                    number = pr["number"]

                    # Each PR gets its own folder so it can resume.
                    folder = review_folder / f"pr_{number}"
                    folder.mkdir(parents=True, exist_ok=True)

                    page = 1

                    while True:
                        filename = folder / f"page_{page:04d}.json"

                        if filename.exists():
                            record = json.loads(filename.read_text())
                            reviews = record["data"]
                            has_next = record["has_next"]
                            print(
                                f"{repo} PR #{number}, page {page}: saved"
                            )
                        else:
                            url = (
                                f"{BASE_URL}/repos/{repo}/pulls/"
                                f"{number}/reviews"
                            )

                            params = {
                                "per_page": PER_PAGE,
                                "page": page
                            }

                            response = fetch(client, url, params)
                            reviews = response.json()
                            has_next = "next" in response.links

                            record = {
                                "repo": repo,
                                "endpoint": "reviews",
                                "pr_number": number,
                                "page": page,
                                "url": str(response.url),
                                "fetched_at": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                                "has_next": has_next,
                                "data": reviews
                            }

                            temp = filename.with_suffix(".tmp")
                            temp.write_text(json.dumps(record))
                            temp.replace(filename)

                            print(
                                f"{repo} PR #{number}, page {page}: "
                                f"{len(reviews)} reviews"
                            )

                        if not has_next:
                            break

                        page += 1

                    processed += 1

                    if MAX_PRS_PER_REPO is not None and processed >= MAX_PRS_PER_REPO:
                        break

                if MAX_PRS_PER_REPO is not None and processed >= MAX_PRS_PER_REPO:
                    break

            print(f"Finished test for {repo}: {processed} PRs")


if __name__ == "__main__":
    main()
