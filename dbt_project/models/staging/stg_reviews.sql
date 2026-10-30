SELECT repo,id AS review_id,
TRY_CAST(regexp_extract(json_extract_string(payload,'$.pull_request_url'),'/([0-9]+)$',1) AS BIGINT) AS pr_number,
json_extract_string(payload,'$.user.login') AS reviewer,
json_extract_string(payload,'$.state') AS review_state,
TRY_CAST(json_extract_string(payload,'$.submitted_at') AS TIMESTAMPTZ) AS submitted_at,
(COALESCE(json_extract_string(payload,'$.user.type'),'')='Bot' OR
COALESCE(json_extract_string(payload,'$.user.login'),'') LIKE '%[bot]') AS is_bot
FROM {{ source('github','raw_pr_reviews') }}
WHERE UPPER(COALESCE(json_extract_string(payload,'$.state'),'')) <> 'PENDING'
QUALIFY ROW_NUMBER() OVER(PARTITION BY repo,id ORDER BY fetched_at DESC)=1