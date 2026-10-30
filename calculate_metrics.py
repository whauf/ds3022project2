
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = "data/package_health.duckdb"
OUTPUT_PATH = Path("data/repository_metrics.csv")

START_DATE = "2024-01-01"


def main():
    con = duckdb.connect(DB_PATH, read_only=True)

    query = """
    WITH commits AS (
        SELECT
            repo,
            COUNT(*) AS commit_count,
            COUNT(DISTINCT author_name) AS contributors
        FROM stg_commits
        WHERE TRY_CAST(committed_at AS TIMESTAMP)
              >= TIMESTAMP '2024-01-01'
        GROUP BY repo
    ),

    pulls AS (
        SELECT
            repo,
            COUNT(*) FILTER (
                WHERE merged_at IS NOT NULL
                  AND TRY_CAST(merged_at AS TIMESTAMP)
                      >= TIMESTAMP '2024-01-01'
            ) AS merged_prs,
            COUNT(*) FILTER (
                WHERE TRY_CAST(created_at AS TIMESTAMP)
                      >= TIMESTAMP '2024-01-01'
            ) AS recent_prs
        FROM stg_pull_requests
        GROUP BY repo
    ),

    reviews AS (
        SELECT
            repo,
            COUNT(*) AS review_count
        FROM stg_reviews
        WHERE TRY_CAST(submitted_at AS TIMESTAMP)
              >= TIMESTAMP '2024-01-01'
        GROUP BY repo
    ),

    release_dates AS (
        SELECT
            repo,
            TRY_CAST(published_at AS TIMESTAMP) AS published_date
        FROM stg_releases
        WHERE is_draft = FALSE
          AND TRY_CAST(published_at AS TIMESTAMP)
              >= TIMESTAMP '2024-01-01'
    ),

    release_intervals AS (
        SELECT
            repo,
            published_date,
            DATE_DIFF(
                'day',
                LAG(published_date) OVER (
                    PARTITION BY repo
                    ORDER BY published_date
                ),
                published_date
            ) AS days_between
        FROM release_dates
    ),

    releases AS (
        SELECT
            repo,
            COUNT(*) AS release_count,
            AVG(days_between) AS avg_days_between_releases
        FROM release_intervals
        GROUP BY repo
    )

    SELECT
        c.repo,
        c.commit_count,
        c.contributors,
        COALESCE(p.merged_prs, 0) AS merged_prs,
        COALESCE(p.recent_prs, 0) AS recent_prs,
        COALESCE(r.review_count, 0) AS review_count,
        COALESCE(
            CAST(r.review_count AS DOUBLE)
            / NULLIF(p.recent_prs, 0),
            0
        ) AS reviews_per_pr,
        COALESCE(rel.release_count, 0) AS release_count,
        rel.avg_days_between_releases
    FROM commits c
    LEFT JOIN pulls p USING (repo)
    LEFT JOIN reviews r USING (repo)
    LEFT JOIN releases rel USING (repo)
    ORDER BY c.repo
    """

    df = con.execute(query).df()
    con.close()

    # Rank repositories on each metric.
    # Higher is better, except days between releases.
    positive_metrics = [
        "commit_count",
        "contributors",
        "merged_prs",
        "reviews_per_pr",
        "release_count",
    ]

    for metric in positive_metrics:
        df[f"{metric}_score"] = (
            df[metric].rank(pct=True) * 100
        )

    df["release_frequency_score"] = (
        df["avg_days_between_releases"]
        .rank(ascending=False, pct=True)
        * 100
    ).fillna(0)

    score_columns = [
        f"{metric}_score" for metric in positive_metrics
    ] + ["release_frequency_score"]

    df["overall_health_score"] = (
        df[score_columns].mean(axis=1)
    ).round(2)

    df["overall_rank"] = (
        df["overall_health_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    df = df.sort_values("overall_rank")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print("\nRepository Health Rankings:")
    print(
        df[
            [
                "repo",
                "commit_count",
                "merged_prs",
                "contributors",
                "reviews_per_pr",
                "release_count",
                "overall_health_score",
                "overall_rank",
            ]
        ].to_string(index=False)
    )

    print(f"\nSaved metrics to {OUTPUT_PATH}")
    print(
        "\nNOTE: Review coverage is incomplete. "
        "Review-based scores are provisional."
    )


if __name__ == "__main__":
    main()
