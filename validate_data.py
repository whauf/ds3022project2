"""Post-dbt completeness and descriptive checks; deliberately does not call dbt."""
import json
from pathlib import Path
import duckdb

DB="data/package_health.duckdb"
TABLES={"commits":("raw_commits","stg_commits"),"pulls":("raw_pull_requests","stg_pull_requests"),"reviews":("raw_pr_reviews","stg_reviews"),"releases":("raw_releases","stg_releases")}

def validate():
    db=duckdb.connect(DB,read_only=True)
    problems=[]
    for endpoint,(raw,stg) in TABLES.items():
        landed=set()
        for file in Path("data/raw").glob(f"*/{endpoint}/**/page_*.json"):
            doc=json.loads(file.read_text())
            for obj in doc["data"]:
                key=obj.get("sha") if endpoint=="commits" else (obj.get("number") if endpoint=="pulls" else obj.get("id"))
                if key is not None:
                    landed.add((doc["repo"],str(key)))
        stored={(repo,str(id)) for repo,id in db.execute(f"SELECT repo,id FROM {raw}").fetchall()}
        missing=landed-stored
        raw_count=len(stored)
        stg_count=db.execute(f"SELECT COUNT(*) FROM {stg}").fetchone()[0]
        print(f"{endpoint}: landed={len(landed)} raw={raw_count} stage={stg_count}, missing={len(missing)}")
        if missing: problems.append(f"{endpoint}: {len(missing)} missing loaded IDs")
        # PENDING reviews and draft releases are intentionally removed in staging
        if endpoint in ("commits","pulls") and raw_count!=stg_count:
            problems.append(f"{endpoint}: raw/staged count mismatch")
    for repo,n in db.execute("""
       SELECT repo,COUNT(*) FROM mart_repo_monthly
       WHERE is_partial_month=FALSE AND commits=0 GROUP BY repo
    """).fetchall():
        problems.append(f"{repo}: {n} complete months without commits")
    print("\nDescriptive statistics (hours):")
    q="""
    SELECT repo,
    median(hours_to_first_review) median_review,
    quantile_cont(hours_to_first_review,0.9) p90_review,
    median(hours_to_merge) median_merge,
    quantile_cont(hours_to_merge,0.9) p90_merge
    FROM fct_pull_requests GROUP BY repo ORDER BY repo
    """
    for row in db.execute(q).fetchall(): print(row)
    print("\nAnnualized rates:")
    for row in db.execute("SELECT repo,commits_per_week,releases_per_year FROM mart_health_inputs ORDER BY repo").fetchall():print(row)
    print("\nOutliers: merged PRs with more than one year to merge (kept; long-lived work is real):")
    for row in db.execute("""
       SELECT repo,pr_number,hours_to_merge FROM fct_pull_requests
       WHERE hours_to_merge > 24*365 ORDER BY hours_to_merge DESC LIMIT 30
    """).fetchall():print(row)
    print("\nWeekly commit spikes: weeks exceeding mean + 3 standard deviations (kept):")
    for row in db.execute("""
    WITH w AS (
     SELECT repo,date_trunc('week',committed_at) AS week,COUNT(*) AS commits
     FROM stg_commits WHERE committed_at >= TIMESTAMPTZ '2024-01-01' GROUP BY 1,2
    ), b AS (
     SELECT *,avg(commits) OVER(PARTITION BY repo) mean_commits,
     stddev_pop(commits) OVER(PARTITION BY repo) sd_commits FROM w
    )
    SELECT repo,week,commits FROM b WHERE commits > mean_commits + 3*sd_commits
    ORDER BY repo,week
    """).fetchall():print(row)
    db.close()
    if problems:raise RuntimeError("Validation failed: "+"; ".join(problems))
    print("\nValidation passed")
if __name__=="__main__": validate()
