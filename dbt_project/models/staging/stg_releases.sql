SELECT repo,id AS release_id,
json_extract_string(payload,'$.tag_name') AS tag_name,
json_extract_string(payload,'$.name') AS release_name,
TRY_CAST(json_extract_string(payload,'$.published_at') AS TIMESTAMPTZ) AS published_at,
COALESCE(TRY_CAST(json_extract_string(payload,'$.prerelease') AS BOOLEAN),FALSE) AS is_prerelease,
COALESCE(TRY_CAST(json_extract_string(payload,'$.draft') AS BOOLEAN),FALSE) AS is_draft,
FALSE AS is_bot
FROM {{ source('github','raw_releases') }}
WHERE COALESCE(TRY_CAST(json_extract_string(payload,'$.draft') AS BOOLEAN),FALSE)=FALSE
QUALIFY ROW_NUMBER() OVER(PARTITION BY repo,id ORDER BY fetched_at DESC)=1