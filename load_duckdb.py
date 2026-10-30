
import json
from pathlib import Path

import duckdb

REPOS = [
    "numpy/numpy",
    "networkx/networkx",
    "statsmodels/statsmodels",
]

ENDPOINTS = ["commits", "pulls", "releases", "reviews"]

DB_PATH = "data/package_health.duckdb"


def main():
    Path("data").mkdir(exist_ok=True)
    con = duckdb.connect(DB_PATH)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_github (
            repo VARCHAR,
            endpoint VARCHAR,
            record_id VARCHAR,
            pr_number BIGINT,
            payload JSON
        )
    """)

    # Rebuild from saved JSON files to avoid duplicates.
    con.execute("DELETE FROM raw_github")

    for repo in REPOS:
        repo_folder = Path("data/raw") / repo.replace("/", "__")

        for endpoint in ENDPOINTS:
            folder = repo_folder / endpoint
            if not folder.exists():
                print(f"Skipping missing folder: {folder}")
                continue

            files = sorted(folder.rglob("page_*.json"))
            records = []

            for file in files:
                saved = json.loads(file.read_text())
                data = saved.get("data", [])

                if not isinstance(data, list):
                    continue

                pr_number = saved.get("pr_number")

                for item in data:
                    record_id = str(
                        item.get("id")
                        or item.get("sha")
                        or item.get("tag_name")
                        or ""
                    )

                    records.append((
                        repo,
                        endpoint,
                        record_id,
                        pr_number,
                        json.dumps(item),
                    ))

            if records:
                con.executemany(
                    """
                    INSERT INTO raw_github
                    (repo, endpoint, record_id, pr_number, payload)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    records,
                )

            print(f"{repo} | {endpoint}: {len(records)} records loaded")

    print("\nDatabase summary:")
    results = con.execute("""
        SELECT repo, endpoint, COUNT(*) AS total
        FROM raw_github
        GROUP BY repo, endpoint
        ORDER BY repo, endpoint
    """).fetchall()

    for repo, endpoint, total in results:
        print(f"{repo} | {endpoint}: {total}")

    con.close()
    print(f"\nDatabase created: {DB_PATH}")


if __name__ == "__main__":
    main()
