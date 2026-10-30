
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = "data/repository_metrics.csv"
OUTPUT_DIR = Path("outputs/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH)
df["name"] = df["repo"].str.split("/").str[-1]

# Plot 1: Development activity
fig, ax = plt.subplots(figsize=(9, 6))

scatter = ax.scatter(
    df["commit_count"],
    df["merged_prs"],
    s=df["contributors"] * 2,
    c=df["overall_health_score"],
    cmap="viridis",
    alpha=0.75,
    edgecolors="black"
)

for _, row in df.iterrows():
    ax.annotate(
        row["name"],
        (row["commit_count"], row["merged_prs"]),
        xytext=(8, 8),
        textcoords="offset points"
    )

ax.set_xlabel("Commits since January 2024")
ax.set_ylabel("Merged pull requests since January 2024")
ax.set_title("Development Activity vs. Merged PRs")

fig.colorbar(scatter, ax=ax, label="Health score")
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "development_activity.png", dpi=300)
plt.close(fig)


# Plot 2: Collaboration vs. release activity
fig, ax = plt.subplots(figsize=(9, 6))

scatter = ax.scatter(
    df["reviews_per_pr"],
    df["release_count"],
    s=df["contributors"] * 2,
    c=df["overall_health_score"],
    cmap="plasma",
    alpha=0.75,
    edgecolors="black"
)

for _, row in df.iterrows():
    ax.annotate(
        row["name"],
        (row["reviews_per_pr"], row["release_count"]),
        xytext=(8, 8),
        textcoords="offset points"
    )

ax.set_xlabel("Observed reviews per PR (partial data)")
ax.set_ylabel("Releases since January 2024")
ax.set_title("Collaboration vs. Release Activity")

fig.colorbar(scatter, ax=ax, label="Health score")
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "collaboration_releases.png", dpi=300)
plt.close(fig)


# Plot 3: Repository health score breakdown
score_columns = [
    "commit_count_score",
    "contributors_score",
    "merged_prs_score",
    "reviews_per_pr_score",
    "release_count_score",
    "release_frequency_score"
]

score_labels = [
    "Commits",
    "Contributors",
    "Merged PRs",
    "Reviews/PR",
    "Releases",
    "Release frequency"
]

plot_df = df.set_index("name")[score_columns]
plot_df.columns = score_labels

ax = plot_df.T.plot(
    kind="bar",
    figsize=(11, 6),
    width=0.75
)

ax.set_title("Repository Health: Metric Score Comparison")
ax.set_xlabel("Health metric")
ax.set_ylabel("Relative metric score")
ax.set_ylim(0, 105)
ax.legend(title="Repository")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "health_score_comparison.png", dpi=300)
plt.close()

print("Successfully created 3 visualizations:")
for filename in [
    "development_activity.png",
    "collaboration_releases.png",
    "health_score_comparison.png"
]:
    print(f"  {OUTPUT_DIR / filename}")
