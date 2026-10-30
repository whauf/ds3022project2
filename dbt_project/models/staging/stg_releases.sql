
SELECT
    repo,
    record_id AS release_id,
    json_extract_string(payload, '$.tag_name') AS tag_name,
    json_extract_string(payload, '$.name') AS release_name,
    json_extract_string(payload, '$.published_at') AS published_at,
    TRY_CAST(json_extract_string(payload, '$.prerelease') AS BOOLEAN) AS is_prerelease,
    TRY_CAST(json_extract_string(payload, '$.draft') AS BOOLEAN) AS is_draft
FROM raw_github
WHERE endpoint = 'releases'
