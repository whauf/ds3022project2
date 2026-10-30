
SELECT
    repo,
    record_id AS commit_sha,
    json_extract_string(payload, '$.commit.author.date') AS committed_at,
    json_extract_string(payload, '$.commit.author.name') AS author_name,
    json_extract_string(payload, '$.commit.message') AS message
FROM raw_github
WHERE endpoint = 'commits'
