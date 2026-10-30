SELECT repo,TRY_CAST(id AS BIGINT) AS pr_number,
json_extract_string(payload,'$.state') AS state,
TRY_CAST(json_extract_string(payload,'$.created_at') AS TIMESTAMPTZ) AS created_at,
TRY_CAST(json_extract_string(payload,'$.updated_at') AS TIMESTAMPTZ) AS updated_at,
TRY_CAST(json_extract_string(payload,'$.closed_at') AS TIMESTAMPTZ) AS closed_at,
TRY_CAST(json_extract_string(payload,'$.merged_at') AS TIMESTAMPTZ) AS merged_at,
json_extract_string(payload,'$.user.login') AS author,
json_extract_string(payload,'$.title') AS title,
TRY_CAST(json_extract_string(payload,'$.draft') AS BOOLEAN) AS is_draft,
(COALESCE(json_extract_string(payload,'$.user.type'),'')='Bot' OR
COALESCE(json_extract_string(payload,'$.user.login'),'') LIKE '%[bot]') AS is_bot
FROM {{ source('github','raw_pull_requests') }}
QUALIFY ROW_NUMBER() OVER(PARTITION BY repo,id ORDER BY fetched_at DESC)=1