"""Idempotent JSON -> DuckDB ingestion with endpoint-specific tables."""
import json
from pathlib import Path
from datetime import datetime, timezone
import duckdb

DB_PATH = Path("data/package_health.duckdb")
ENDPOINT_TABLES = {
    "commits": "raw_commits",
    "pulls": "raw_pull_requests",
    "reviews": "raw_pr_reviews",
    "releases": "raw_releases",
}

def parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

def load():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        for table in ENDPOINT_TABLES.values():
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    repo VARCHAR NOT NULL,
                    id VARCHAR NOT NULL,
                    updated_at TIMESTAMPTZ,
                    fetched_at TIMESTAMPTZ,
                    source_file VARCHAR,
                    payload JSON,
                    PRIMARY KEY (repo,id)
                )
            """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS _load_state (
                repo VARCHAR,
                endpoint VARCHAR,
                newest_updated_at TIMESTAMPTZ,
                loaded_at TIMESTAMPTZ,
                PRIMARY KEY (repo,endpoint)
            )
        """)
        # Keep all changes atomic, including watermarks.
        con.execute("BEGIN TRANSACTION")
        counts = {}
        for endpoint,table in ENDPOINT_TABLES.items():
            for filepath in sorted(Path("data/raw").glob(f"*/{endpoint}/**/page_*.json")):
                saved = json.loads(filepath.read_text())
                repo = saved["repo"]
                data = saved["data"]
                if not isinstance(data,list):
                    raise ValueError(f"Expected JSON list in {filepath}")
                fetched = parse_timestamp(saved.get("fetched_at"))
                for item in data:
                    key = item.get("sha") if endpoint == "commits" else (
                        item.get("number") if endpoint == "pulls" else item.get("id")
                    )
                    if key is None:
                        raise ValueError(f"Missing record ID: {filepath}")
                    updated = parse_timestamp(
                        item.get("updated_at") or item.get("submitted_at")
                        or item.get("published_at") or item.get("commit",{}).get("author",{}).get("date")
                    )
                    con.execute(f"""
                        INSERT INTO {table}
                        (repo,id,updated_at,fetched_at,source_file,payload)
                        VALUES (?,?,?,?,?,?)
                        ON CONFLICT (repo,id) DO UPDATE SET
                          updated_at=excluded.updated_at,
                          fetched_at=excluded.fetched_at,
                          source_file=excluded.source_file,
                          payload=excluded.payload
                    """,[repo,str(key),updated,fetched,str(filepath),json.dumps(item)])
                    counts[(repo,endpoint)] = counts.get((repo,endpoint),0)+1
        for (repo,endpoint),count in sorted(counts.items()):
            table=ENDPOINT_TABLES[endpoint]
            con.execute("""
                INSERT INTO _load_state(repo,endpoint,newest_updated_at,loaded_at)
                SELECT ?,?,MAX(updated_at),? FROM """+table+""" WHERE repo=?
                ON CONFLICT (repo,endpoint) DO UPDATE SET
                newest_updated_at=excluded.newest_updated_at,
                loaded_at=excluded.loaded_at
            """,[repo,endpoint,datetime.now(timezone.utc),repo])
            total=con.execute(f"SELECT COUNT(*) FROM {table} WHERE repo=?",[repo]).fetchone()[0]
            print(f"{repo} {endpoint}: {count} landed records; {total} unique database records")
        con.execute("COMMIT")
        Path("data/raw/_LOADED").touch()
        print(f"Load completed: {DB_PATH}")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

if __name__ == "__main__":
    load()
