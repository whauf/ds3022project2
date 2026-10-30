WITH base AS (
 SELECT p.*, TRY_CAST(p.created_at AS TIMESTAMPTZ) created_ts,
 TRY_CAST(p.updated_at AS TIMESTAMPTZ) updated_ts,
 TRY_CAST(p.closed_at AS TIMESTAMPTZ) closed_ts,
 TRY_CAST(p.merged_at AS TIMESTAMPTZ) merged_ts
 FROM {{ ref('stg_pull_requests') }} p
 WHERE TRY_CAST(p.created_at AS TIMESTAMPTZ) >= TIMESTAMPTZ '2024-01-01'
),
review_first AS (
 SELECT p.repo,p.pr_number,
 MIN(TRY_CAST(r.submitted_at AS TIMESTAMPTZ)) AS first_review_at,
 BOOL_OR(UPPER(r.review_state) = 'APPROVED') AS has_approving_review
 FROM base p LEFT JOIN {{ ref('stg_reviews') }} r
 ON p.repo=r.repo AND p.pr_number=r.pr_number
 AND COALESCE(r.reviewer,'') <> COALESCE(p.author,'')
 AND COALESCE(r.reviewer,'') NOT LIKE '%[bot]'
 AND TRY_CAST(r.submitted_at AS TIMESTAMPTZ) IS NOT NULL
 GROUP BY 1,2
),
runtime AS (
 SELECT MAX(TRY_CAST(fetched_at AS TIMESTAMPTZ)) AS run_at
 FROM {{ source('github','raw_pull_requests') }}
)
SELECT b.repo,b.pr_number,b.author,b.state,b.created_ts AS created_at,
b.updated_ts AS updated_at,b.closed_ts AS closed_at,b.merged_ts AS merged_at,
b.merged_ts IS NOT NULL AS is_merged,
b.state='closed' AND b.merged_ts IS NULL AS is_closed_unmerged,
b.state='open' AS is_open,
r.first_review_at,
date_diff('second',b.created_ts,r.first_review_at)/3600.0 AS hours_to_first_review,
COALESCE(date_diff('second',b.created_ts,r.first_review_at)/3600.0 <=168,FALSE) AS reviewed_within_7d,
CASE WHEN b.merged_ts IS NOT NULL THEN date_diff('second',b.created_ts,b.merged_ts)/3600.0 END AS hours_to_merge,
CASE WHEN b.closed_ts IS NOT NULL THEN date_diff('second',b.created_ts,b.closed_ts)/3600.0 END AS hours_to_close,
b.state='open' AND b.updated_ts < runtime.run_at-INTERVAL '180 days' AS is_stale,
COALESCE(r.has_approving_review,FALSE) AS has_approving_review
FROM base b LEFT JOIN review_first r USING(repo,pr_number)
CROSS JOIN runtime