
import os
import json
import time
import httpx

from pathlib import Path
from datetime import datetime, timezone

REPOS = [
    "numpy/numpy",
    "networkx/networkx",
    "statsmodels/statsmodels"
]

BASE_URL = "https://api.github.com"
PER_PAGE = 100


def main():
    token = os.environ["GITHUB_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    with httpx.Client(headers=headers, timeout=60) as client:
        for repo in REPOS:
            folder = (
                Path("data/raw")
                / repo.replace("/", "__")
                / "releases"
            )
            folder.mkdir(parents=True, exist_ok=True)

            page = 1
            total = 0

            while True:
                filename = folder / f"page_{page:04d}.json"

                if filename.exists():
                    saved = json.loads(filename.read_text())
                    releases = saved["data"]
                    has_next = saved["has_next"]
                    print(f"{repo}: Release page {page} already saved")

                else:
                    url = f"{BASE_URL}/repos/{repo}/releases"

                    params = {
                        "per_page": PER_PAGE,
                        "page": page
                    }

                    for attempt in range(5):
                        response = client.get(url, params=params)

                        if response.status_code in (403, 429):
                            remaining = int(
                                response.headers.get(
                                    "X-RateLimit-Remaining", 1
                                )
                            )
                            if remaining == 0:
                                reset = int(
                                    response.headers.get(
                                        "X-RateLimit-Reset", 0
                                    )
                                )
                                wait = max(
                                    1, reset - time.time() + 5
                                )
                            else:
                                wait = min(60 * (attempt + 1), 300)

                            print(f"Rate limited. Waiting {wait:.0f}s.")
                            time.sleep(wait)
                            continue

                        if response.status_code >= 500:
                            time.sleep(2 ** attempt)
                            continue

                        response.raise_for_status()
                        break
                    else:
                        raise RuntimeError(
                            f"Could not download {repo} releases page {page}"
                        )

                    releases = response.json()
                    has_next = "next" in response.links

                    saved = {
                        "repo": repo,
                        "endpoint": "releases",
                        "page": page,
                        "url": str(response.url),
                        "fetched_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "has_next": has_next,
                        "data": releases
                    }

                    temp = filename.with_suffix(".tmp")
                    temp.write_text(json.dumps(saved))
                    temp.replace(filename)

                    print(
                        f"{repo}: Release page {page} "
                        f"downloaded ({len(releases)} releases)"
                    )

                total += len(releases)

                if not has_next:
                    break

                page += 1

            print(f"Completed {repo}: {total} releases")


if __name__ == "__main__":
    main()
