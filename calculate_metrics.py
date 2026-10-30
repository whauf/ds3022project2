"""Weighted, size-normalized repository health scores from dbt health mart."""
from pathlib import Path
import duckdb
import pandas as pd

DB="data/package_health.duckdb"
OUT=Path("data/repository_metrics.csv")
METRICS={
    "commits_per_week":("activity",True,0.10),
    "commit_trend":("activity",True,0.15),
    "pct_reviewed_within_7d":("responsiveness",True,0.20),
    "median_hours_to_merge":("throughput",False,0.15),
    "merge_rate":("throughput",True,0.15),
    "pct_stale_open_prs":("backlog",False,0.10),
    "releases_per_year":("release_cadence",True,0.15),
}
def main():
    conn=duckdb.connect(DB)
    try:
        df=conn.execute("SELECT * FROM mart_health_inputs ORDER BY repo").df()
        if len(df)!=3:
            raise ValueError(f"Expected three repositories, found {len(df)}")
        dimensions=sorted(set(v[0] for v in METRICS.values()))
        weighted={}
        for metric,(dimension,higher,weight) in METRICS.items():
            x=pd.to_numeric(df[metric],errors="coerce")
            if x.isna().all():
                raise ValueError(f"No values for required metric: {metric}")
            # Midpoint for an unavailable value; zero variance => neutral 50.
            lo,hi=x.min(),x.max()
            scores=pd.Series(50.0,index=x.index) if lo==hi else (x-lo)/(hi-lo)*100
            if not higher:scores=100-scores
            scores=scores.fillna(50)
            df[metric+"_score"]=scores.round(2)
            weighted[metric]=scores*weight
        for d in dimensions:
            included=[m for m,defn in METRICS.items() if defn[0]==d]
            total_weight=sum(METRICS[m][2] for m in included)
            df[d+"_score"]=sum(weighted[m] for m in included)/total_weight
        df["overall_health_score"]=sum(weighted.values()).round(2)
        df["overall_rank"]=df["overall_health_score"].rank(ascending=False,method="min").astype(int)
        df=df.sort_values(["overall_rank","repo"])
        OUT.parent.mkdir(exist_ok=True,parents=True)
        df.to_csv(OUT,index=False)
        conn.execute("CREATE OR REPLACE TABLE repository_health_rankings AS SELECT * FROM df")
        cols=["repo","overall_rank","overall_health_score"]+[d+"_score" for d in dimensions]
        print(df[cols].to_string(index=False))
        print("Saved ranked table and",OUT)
    finally:
        conn.close()
if __name__=="__main__":main()
