WITH duplicates AS (
 SELECT 'commits' AS source,repo,commit_sha AS id,COUNT(*) n FROM {{ ref('stg_commits') }} GROUP BY 1,2,3 HAVING COUNT(*)>1
 UNION ALL
 SELECT 'pulls',repo,CAST(pr_number AS VARCHAR),COUNT(*) FROM {{ ref('stg_pull_requests') }} GROUP BY 1,2,3 HAVING COUNT(*)>1
 UNION ALL
 SELECT 'reviews',repo,review_id,COUNT(*) FROM {{ ref('stg_reviews') }} GROUP BY 1,2,3 HAVING COUNT(*)>1
 UNION ALL
 SELECT 'releases',repo,release_id,COUNT(*) FROM {{ ref('stg_releases') }} GROUP BY 1,2,3 HAVING COUNT(*)>1
)
SELECT * FROM duplicates