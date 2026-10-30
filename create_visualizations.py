"""Rubric plots: dimension comparison, monthly trends, 3-variable relationship."""
from pathlib import Path
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
OUT=Path("plots")
OUT.mkdir(exist_ok=True,parents=True)
scores=pd.read_csv("data/repository_metrics.csv").sort_values("overall_rank")
conn=duckdb.connect("data/package_health.duckdb",read_only=True)
months=conn.execute("SELECT * FROM mart_repo_monthly ORDER BY month").df()
conn.close()
colors={r:c for r,c in zip(sorted(scores.repo),["#2064ab","#c56620","#48844c"])}
dimensions=["activity","responsiveness","throughput","backlog","release_cadence"]
fig,ax=plt.subplots(figsize=(11,6))
x=range(len(dimensions))
for _,r in scores.iterrows():
    ax.plot(x,[r[d+"_score"] for d in dimensions],marker="o",linewidth=2.2,
            color=colors[r.repo],label=f"#{int(r.overall_rank)} {r.repo}: {r.overall_health_score:.1f}")
ax.set_xticks(list(x),["Activity","Responsiveness","Throughput","Backlog","Release cadence"])
ax.set_ylabel("Dimension score (0–100)")
ax.set_ylim(0,105)
ax.set_title("Package Health Dimension Profile")
ax.grid(axis="y",alpha=.25)
ax.legend(fontsize=9)
fig.tight_layout();fig.savefig(OUT/"dimension_profile.png",dpi=200);plt.close(fig)

fig,axes=plt.subplots(3,1,figsize=(11,10),sharex=True)
for ax,(column,label) in zip(axes,[("commits","Monthly commits"),("prs_opened","New PRs"),("prs_merged","Merged PRs")]):
    for repo,part in months.groupby("repo"):
        ax.plot(part["month"],part[column],label=repo,color=colors[repo],linewidth=1.8)
    ax.set_ylabel(label+" (count)")
    ax.grid(alpha=.2)
axes[0].legend()
axes[-1].set_xlabel("Calendar month (2024 to run month)")
fig.suptitle("Monthly Development Trends")
fig.tight_layout();fig.savefig(OUT/"monthly_trends.png",dpi=200);plt.close(fig)

fig,ax=plt.subplots(figsize=(10,6))
for _,r in scores.iterrows():
    x=r.pct_reviewed_within_7d*100 if pd.notna(r.pct_reviewed_within_7d) else 0
    y=r.merge_rate*100 if pd.notna(r.merge_rate) else 0
    size=max(50,float(r.commits_per_week)*18)
    ax.scatter(x,y,s=size,color=colors[r.repo],edgecolors="black",alpha=.7,label=r.repo)
    ax.annotate(r.repo.split("/")[-1],(x,y),xytext=(7,7),textcoords="offset points")
ax.set_xlabel("PRs reviewed within 7 days (%)")
ax.set_ylabel("Merge rate (%)")
ax.set_title("Response, Throughput and Activity (bubble area ∝ commits/week)")
ax.set_xlim(-5,105);ax.set_ylim(-5,105)
ax.grid(alpha=.2);ax.legend()
fig.tight_layout();fig.savefig(OUT/"health_relationship.png",dpi=200);plt.close(fig)
print("Created:",*[str(x) for x in sorted(OUT.glob("*.png"))],sep="\n")
