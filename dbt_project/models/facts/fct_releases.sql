WITH all_releases AS (
 SELECT repo,release_id,tag_name,TRY_CAST(published_at AS TIMESTAMPTZ) AS published_at,is_prerelease,
 LAG(TRY_CAST(published_at AS TIMESTAMPTZ)) OVER (PARTITION BY repo ORDER BY TRY_CAST(published_at AS TIMESTAMPTZ)) AS previous_release_at
 FROM {{ ref('stg_releases') }} WHERE COALESCE(is_draft,FALSE)=FALSE AND published_at IS NOT NULL
)
SELECT repo,release_id,tag_name,published_at,is_prerelease,
date_diff('day',previous_release_at,published_at) AS days_since_previous
FROM all_releases WHERE published_at >= TIMESTAMPTZ '2024-01-01'