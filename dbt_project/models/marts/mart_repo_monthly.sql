WITH runtime AS (
 SELECT COALESCE(MAX(TRY_CAST(fetched_at AS TIMESTAMPTZ)),now()) AS run_at
 FROM {{ source('github','raw_pull_requests') }}
), repo_list AS (
 SELECT unnest(['numpy/numpy','networkx/networkx','statsmodels/statsmodels']) AS repo
), months AS (
 SELECT unnest(generate_series(DATE '2024-01-01',
 date_trunc('month',(SELECT run_at FROM runtime))::DATE, INTERVAL '1 month'))::DATE AS month
), grid AS (
 SELECT r.repo,m.month FROM repo_list r CROSS JOIN months m
), opened AS (
 SELECT repo,date_trunc('month',created_at)::DATE AS month,
 COUNT(*) AS prs_opened,
 MEDIAN(hours_to_first_review) AS median_first_review_hours,
 COUNT(DISTINCT CASE WHEN author NOT LIKE '%[bot]' THEN author END) AS active_contributors
 FROM {{ ref('fct_pull_requests') }} GROUP BY 1,2
), merged AS (
 SELECT repo,date_trunc('month',merged_at)::DATE AS month,
 COUNT(*) AS prs_merged,MEDIAN(hours_to_merge) AS median_merge_hours
 FROM {{ ref('fct_pull_requests') }} WHERE is_merged GROUP BY 1,2
), closed AS (
 SELECT repo,date_trunc('month',closed_at)::DATE AS month,COUNT(*) AS prs_closed_unmerged
 FROM {{ ref('fct_pull_requests') }} WHERE is_closed_unmerged GROUP BY 1,2
), commits AS (
 SELECT repo,date_trunc('month',TRY_CAST(committed_at AS TIMESTAMPTZ))::DATE month,COUNT(*) commits
 FROM {{ ref('stg_commits') }}
 WHERE TRY_CAST(committed_at AS TIMESTAMPTZ)>=TIMESTAMPTZ '2024-01-01'
 GROUP BY 1,2
)
SELECT g.repo,g.month,
COALESCE(o.prs_opened,0) prs_opened,COALESCE(m.prs_merged,0) prs_merged,
COALESCE(c.prs_closed_unmerged,0) prs_closed_unmerged,
COALESCE(m.prs_merged,0)::DOUBLE/
NULLIF(COALESCE(m.prs_merged,0)+COALESCE(c.prs_closed_unmerged,0),0) AS merge_ratio,
o.median_first_review_hours,m.median_merge_hours,
COALESCE(k.commits,0) commits,COALESCE(o.active_contributors,0) active_contributors,
g.month=date_trunc('month',(SELECT run_at FROM runtime))::DATE AS is_partial_month
FROM grid g
LEFT JOIN opened o USING(repo,month)
LEFT JOIN merged m USING(repo,month)
LEFT JOIN closed c USING(repo,month)
LEFT JOIN commits k USING(repo,month)