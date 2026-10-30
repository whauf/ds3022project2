SELECT r.repo,r.review_id FROM {{ ref('stg_reviews') }} r
JOIN {{ ref('stg_pull_requests') }} p
ON r.repo=p.repo AND r.pr_number=p.pr_number
WHERE r.submitted_at < p.created_at