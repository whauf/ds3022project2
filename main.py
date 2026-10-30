import sys

import os
import json
import time
import httpx
import subprocess

from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs
from prefect import flow, task, get_run_logger


# Set A repositories
REPOS = [
    "numpy/numpy",
    "networkx/networkx",
    "statsmodels/statsmodels"
]

START_DATE = "2024-01-01T00:00:00Z"
BASE_URL = "https://api.github.com"
PER_PAGE = 100


def fetch_page(client, url, headers, params):
    """Fetch a GitHub API page with retries and rate-limit handling."""

    logger = get_run_logger()

    for attempt in range(5):
        try:
            response = client.get(
                url,
                headers=headers,
                params=params
            )

            remaining = int(
                response.headers.get("X-RateLimit-Remaining", 5000)
            )
            reset = int(
                response.headers.get("X-RateLimit-Reset", 0)
            )

            if response.status_code in (403, 429):
                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        retry_date = parsedate_to_datetime(
                            retry_after
                        )
                        wait = (
                            retry_date -
                            datetime.now(timezone.utc)
                        ).total_seconds()
                elif remaining == 0:
                    wait = reset - time.time() + 5
                else:
                    wait = 60 * (attempt + 1)

                wait = max(1, wait)

                logger.warning(
                    f"GitHub rate limit. "
                    f"Waiting {wait:.0f} seconds."
                )
                time.sleep(wait)
                continue

            response.raise_for_status()

            if remaining <= 1:
                wait = max(0, reset - time.time() + 5)

                logger.warning(
                    f"API quota nearly exhausted. "
                    f"Waiting {wait:.0f} seconds."
                )
                time.sleep(wait)

            return response

        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            if isinstance(error, httpx.HTTPStatusError):
                if error.response.status_code < 500:
                    raise

            if attempt == 4:
                raise

            wait = 2 ** attempt

            logger.warning(
                f"Request failed: {error}. "
                f"Retrying in {wait} seconds."
            )

            time.sleep(wait)

    raise RuntimeError(
        "GitHub request failed after retries"
    )


def page_path(repo, endpoint, page):
    """Return the JSON file location."""

    folder = (
        Path("data/raw")
        / repo.replace("/", "__")
        / endpoint
    )

    folder.mkdir(parents=True, exist_ok=True)

    return folder / f"page_{page:04d}.json"


def save_page(repo, endpoint, page, url, data, has_next):
    """Save a page and its pagination metadata safely."""

    filename = page_path(repo, endpoint, page)
    temp_file = filename.with_suffix(".tmp")

    result = {
        "repo": repo,
        "endpoint": endpoint,
        "url": url,
        "page": page,
        "fetched_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "has_next": has_next,
        "data": data
    }

    with open(temp_file, "w") as file:
        json.dump(result, file)

    temp_file.replace(filename)

    return filename


def load_saved_page(repo, endpoint, page):
    """Reuse only valid pages with the correct query parameters."""

    filename = page_path(repo, endpoint, page)

    if not filename.exists():
        return None

    try:
        with open(filename) as file:
            saved = json.load(file)

        if (
            saved["repo"] != repo
            or saved["endpoint"] != endpoint
            or saved["page"] != page
            or not isinstance(saved["data"], list)
        ):
            return None

        query = parse_qs(
            urlparse(saved["url"]).query
        )

        # Both endpoints require 100 results per page.
        if (
            query.get("per_page") != [str(PER_PAGE)]
            or int(query.get("page", ["1"])[0]) != page
        ):
            return None

        # Commit-specific parameters
        if endpoint == "commits":
            if query.get("since") != [START_DATE]:
                return None

        # Pull-request-specific parameters
        elif endpoint == "pulls":
            if (
                query.get("state") != ["all"]
                or query.get("sort") != ["updated"]
                or query.get("direction") != ["desc"]
            ):
                return None

        else:
            return None

        # Preserve compatibility with earlier saved commit pages.
        if "has_next" not in saved:
            saved["has_next"] = (
                len(saved["data"]) == PER_PAGE
            )

        return saved

    except (OSError, ValueError, KeyError, TypeError):
        return None


@task(
    name="Extract GitHub Commits",
    retries=3,
    retry_delay_seconds=30
)
def extract_data():
    """Download commits since 2024 for all Set A repositories."""

    logger = get_run_logger()

    token = os.environ["GITHUB_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    total_commits = 0

    with httpx.Client(timeout=60) as client:
        for repo in REPOS:
            logger.info(f"Starting commit extraction: {repo}")

            url = f"{BASE_URL}/repos/{repo}/commits"

            page = 1
            repo_commits = 0

            while True:
                saved = load_saved_page(
                    repo, "commits", page
                )

                if saved is not None:
                    commits = saved["data"]
                    has_next = saved["has_next"]

                    logger.info(
                        f"{repo}: Commit page {page} "
                        f"already saved ({len(commits)} commits)"
                    )

                else:
                    params = {
                        "since": START_DATE,
                        "per_page": PER_PAGE,
                        "page": page
                    }

                    response = fetch_page(
                        client,
                        url,
                        headers,
                        params
                    )

                    commits = response.json()

                    if not isinstance(commits, list):
                        raise ValueError(
                            f"Unexpected commit response for {repo}"
                        )

                    has_next = "next" in response.links

                    save_page(
                        repo,
                        "commits",
                        page,
                        str(response.url),
                        commits,
                        has_next
                    )

                    logger.info(
                        f"{repo}: Commit page {page} "
                        f"downloaded ({len(commits)} commits)"
                    )

                repo_commits += len(commits)

                if not has_next:
                    break

                page += 1

            total_commits += repo_commits

            logger.info(
                f"Completed {repo}: "
                f"{repo_commits} commits"
            )

    logger.info(
        f"Commit extraction finished. "
        f"Total commits: {total_commits}"
    )


@task(
    name="Extract Pull Requests",
    retries=3,
    retry_delay_seconds=30
)
def extract_pull_requests():
    """Download all open and closed PRs, sorted by update time."""

    logger = get_run_logger()

    token = os.environ["GITHUB_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    total_prs = 0

    with httpx.Client(timeout=60) as client:
        for repo in REPOS:
            logger.info(f"Starting PR extraction: {repo}")

            url = f"{BASE_URL}/repos/{repo}/pulls"

            page = 1
            repo_prs = 0

            while True:
                saved = load_saved_page(
                    repo, "pulls", page
                )

                if saved is not None:
                    prs = saved["data"]
                    has_next = saved["has_next"]

                    logger.info(
                        f"{repo}: PR page {page} "
                        f"already saved ({len(prs)} PRs)"
                    )

                else:
                    params = {
                        "state": "all",
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": PER_PAGE,
                        "page": page
                    }

                    response = fetch_page(
                        client,
                        url,
                        headers,
                        params
                    )

                    prs = response.json()

                    if not isinstance(prs, list):
                        raise ValueError(
                            f"Unexpected PR response for {repo}"
                        )

                    has_next = "next" in response.links

                    save_page(
                        repo,
                        "pulls",
                        page,
                        str(response.url),
                        prs,
                        has_next
                    )

                    logger.info(
                        f"{repo}: PR page {page} "
                        f"downloaded ({len(prs)} PRs)"
                    )

                repo_prs += len(prs)

                if not has_next:
                    break

                page += 1

            total_prs += repo_prs

            logger.info(
                f"Completed {repo}: "
                f"{repo_prs} pull requests"
            )

    logger.info(
        f"Pull request extraction finished. "
        f"Total PRs: {total_prs}"
    )


@task(name="Extract Releases", retries=2)
def extract_releases():
    subprocess.run(
        [sys.executable, "extract_releases.py"],
        check=True
    )


@task(name="Check Saved PR Reviews")
def extract_reviews():
    logger = get_run_logger()
    logger.warning(
        "Using previously downloaded PR reviews. "
        "Full review extraction is still incomplete."
    )


@task(name="Load DuckDB", retries=2)
def load_database():
    subprocess.run(
        [sys.executable, "load_duckdb.py"],
        check=True
    )


@task(name="Run dbt Models", retries=2)
def run_dbt():
    subprocess.run(
        ["dbt", "run", "--profiles-dir", "."],
        cwd="dbt_project",
        check=True
    )

@task(name="Calculate Health Metrics", retries=2)
def calculate_health_metrics():
    subprocess.run(
        [sys.executable, "calculate_metrics.py"],
        check=True
    )


@task(name="Create Visualizations", retries=2)
def create_figures():
    subprocess.run(
        [sys.executable, "create_visualizations.py"],
        check=True
    )


@flow(name="package-health-flow")
def package_health_flow():
    logger = get_run_logger()
    logger.info("Starting package health pipeline.")

    # GitHub commits and PRs were already downloaded.
    # Their extraction functions are preserved above.

    extract_releases()
    extract_reviews()
    load_database()
    run_dbt()
    calculate_health_metrics()
    create_figures()

    logger.info("Package health pipeline finished.")


if __name__ == "__main__":
    package_health_flow()
