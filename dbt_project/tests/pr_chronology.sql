SELECT repo,pr_number FROM {{ ref('fct_pull_requests') }}
WHERE (closed_at IS NOT NULL AND closed_at < created_at)
OR (merged_at IS NOT NULL AND merged_at < created_at)