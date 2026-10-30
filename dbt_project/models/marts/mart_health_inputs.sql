WITH runtime AS (
 SELECT COALESCE(MAX(TRY_CAST(fetched_at AS TIMESTAMPTZ)),now()) run_at
 FROM {{ source('github','raw_pull_requests') }}
), repo_list AS (
 SELECT unnest(['numpy/numpy','networkx/networkx','statsmodels/statsmodels']) repo
), pr AS (
 SELECT repo,
 AVG(CASE WHEN created_at <= (SELECT run_at FROM runtime)-INTERVAL '7 days' THEN reviewed_within_7d::INT END) AS pct_reviewed_within_7d,
 MEDIAN(hours_to_merge) AS median_hours_to_merge,
 AVG(CASE WHEN state='open' THEN is_stale::INT END) AS pct_stale_open_prs,
 AVG(CASE WHEN state='closed' THEN is_merged::INT END) AS merge_rate
 FROM {{ ref('fct_pull_requests') }} GROUP BY repo
), cm AS (
 SELECT repo, COUNT(*)::DOUBLE / NULLIF(date_diff('day',TIMESTAMPTZ '2024-01-01',(SELECT run_at FROM runtime))/7.0,0) AS commits_per_week
 FROM {{ ref('stg_commits') }}
 WHERE TRY_CAST(committed_at AS TIMESTAMPTZ)>=TIMESTAMPTZ '2024-01-01'
 GROUP BY repo
), monthly AS (
 SELECT repo,REGR_SLOPE(commits, date_diff('month',DATE '2024-01-01',month)) AS commit_trend
 FROM {{ ref('mart_repo_monthly') }} WHERE is_partial_month=FALSE GROUP BY repo
), rel AS (
 SELECT repo, COUNT(*)::DOUBLE / NULLIF(date_diff('day',TIMESTAMPTZ '2024-01-01',(SELECT run_at FROM runtime))/365.25,0) AS releases_per_year
 FROM {{ ref('fct_releases') }} GROUP BY repo
)
SELECT r.repo,COALESCE(cm.commits_per_week,0) commits_per_week,
COALESCE(monthly.commit_trend,0) commit_trend,
pr.pct_reviewed_within_7d,pr.median_hours_to_merge,pr.pct_stale_open_prs,
pr.merge_rate,COALESCE(rel.releases_per_year,0) releases_per_year
FROM repo_list r LEFT JOIN pr USING(repo) LEFT JOIN cm USING(repo)
LEFT JOIN monthly USING(repo) LEFT JOIN rel USING(repo)