
SELECT
    repo,
    TRY_CAST(json_extract_string(payload, '$.number') AS BIGINT) AS pr_number,
    json_extract_string(payload, '$.state') AS state,
    json_extract_string(payload, '$.created_at') AS created_at,
    json_extract_string(payload, '$.updated_at') AS updated_at,
    json_extract_string(payload, '$.closed_at') AS closed_at,
    json_extract_string(payload, '$.merged_at') AS merged_at,
    json_extract_string(payload, '$.user.login') AS author,
    json_extract_string(payload, '$.title') AS title,
    TRY_CAST(json_extract_string(payload, '$.draft') AS BOOLEAN) AS is_draft
FROM raw_github
WHERE endpoint = 'pulls'
