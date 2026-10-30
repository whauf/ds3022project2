SELECT repo,id AS commit_sha, json_extract_string(payload,'$.author.login') AS author_name,
TRY_CAST(json_extract_string(payload,'$.commit.author.date') AS TIMESTAMPTZ) AS committed_at,
json_extract_string(payload,'$.commit.message') AS message,
(COALESCE(json_extract_string(payload,'$.author.type'),'')='Bot' OR
COALESCE(json_extract_string(payload,'$.author.login'),'') LIKE '%[bot]') AS is_bot
FROM {{ source('github','raw_commits') }}
QUALIFY ROW_NUMBER() OVER(PARTITION BY repo,id ORDER BY fetched_at DESC)=1