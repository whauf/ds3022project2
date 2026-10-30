
SELECT
    repo,
    pr_number,
    record_id AS review_id,
    json_extract_string(payload, '$.user.login') AS reviewer,
    json_extract_string(payload, '$.state') AS review_state,
    json_extract_string(payload, '$.submitted_at') AS submitted_at
FROM raw_github
WHERE endpoint = 'reviews'
