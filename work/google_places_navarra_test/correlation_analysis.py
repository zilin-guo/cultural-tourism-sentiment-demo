import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr


REGION_COLORS = {
    "Navarra": "#1f77b4",
    "Torino": "#ff7f0e",
}


def correlation_row(label, df):
    valid = df[["review_rating_numeric", "sentiment_compound"]].dropna()
    # Spearman is the primary check because star ratings are ordinal.
    spearman = spearmanr(valid["review_rating_numeric"], valid["sentiment_compound"])
    pearson = pearsonr(valid["review_rating_numeric"], valid["sentiment_compound"])
    return {
        "group": label,
        "n_reviews": len(valid),
        "spearman_rho": round(float(spearman.statistic), 4),
        "spearman_p_value": float(spearman.pvalue),
        "pearson_r": round(float(pearson.statistic), 4),
        "pearson_p_value": float(pearson.pvalue),
        "mean_rating": round(valid["review_rating_numeric"].mean(), 3),
        "mean_sentiment_compound": round(valid["sentiment_compound"].mean(), 3),
    }


def plot_rating_sentiment_boxplot(df, out_dir):
    plot_df = df.dropna(subset=["review_rating_numeric", "sentiment_compound"]).copy()
    plot_df["review_rating_label"] = plot_df["review_rating_numeric"].astype(int).astype(str)
    rating_order = ["1", "2", "3", "4", "5"]

    fig, ax = plt.subplots(figsize=(9, 6.2))
    sns.boxplot(
        data=plot_df,
        x="review_rating_label",
        y="sentiment_compound",
        hue="region_short",
        order=rating_order,
        palette=REGION_COLORS,
        showfliers=False,
        ax=ax,
    )
    sns.stripplot(
        data=plot_df,
        x="review_rating_label",
        y="sentiment_compound",
        hue="region_short",
        order=rating_order,
        palette=REGION_COLORS,
        dodge=True,
        alpha=0.22,
        size=2,
        linewidth=0,
        ax=ax,
    )
    ax.axhline(0.05, color="#2f9e44", linestyle="--", linewidth=1)
    ax.axhline(-0.05, color="#c92a2a", linestyle="--", linewidth=1)
    ax.set_title("VADER sentiment score by Google review rating")
    ax.set_xlabel("Google review rating")
    ax.set_ylabel("VADER compound sentiment score")

    handles, labels = ax.get_legend_handles_labels()
    dedup = {}
    for handle, label in zip(handles, labels):
        if label in REGION_COLORS and label not in dedup:
            dedup[label] = handle
    ax.legend_.remove()
    fig.legend(
        dedup.values(),
        dedup.keys(),
        title="Region",
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.0),
        ncol=2,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(out_dir / "rating_sentiment_correlation_boxplot.png", dpi=200)
    plt.close(fig)


def plot_rating_sentiment_regression(df, out_dir):
    plot_df = df.dropna(subset=["review_rating_numeric", "sentiment_compound"]).copy()

    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    for region, region_df in plot_df.groupby("region_short"):
        sns.regplot(
            data=region_df,
            x="review_rating_numeric",
            y="sentiment_compound",
            x_jitter=0.08,
            scatter_kws={"alpha": 0.25, "s": 18},
            line_kws={"linewidth": 2.5},
            color=REGION_COLORS.get(region, "#495057"),
            label=region,
            ax=ax,
        )

    ax.set_title("Correlation between star ratings and text sentiment")
    ax.set_xlabel("Google review rating")
    ax.set_ylabel("VADER compound sentiment score")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.axhline(0.05, color="#2f9e44", linestyle="--", linewidth=1)
    ax.axhline(-0.05, color="#c92a2a", linestyle="--", linewidth=1)

    handles, labels = ax.get_legend_handles_labels()
    if ax.legend_:
        ax.legend_.remove()
    fig.legend(
        handles,
        labels,
        title="Region",
        loc="lower center",
        bbox_to_anchor=(0.5, 0.0),
        ncol=2,
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(out_dir / "rating_sentiment_correlation_scatter.png", dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Correlate Google review ratings with VADER sentiment scores."
    )
    parser.add_argument(
        "--input",
        default="outputs/google_places_navarra_torino_analysis/analyzed_reviews.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/google_places_navarra_torino_analysis",
    )
    args = parser.parse_args()

    sns.set_theme(style="whitegrid", font_scale=1.0)
    df = pd.read_csv(args.input)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [correlation_row("All reviews", df)]
    for region, region_df in df.groupby("region_short"):
        rows.append(correlation_row(region, region_df))

    result = pd.DataFrame(rows)
    result.to_csv(out_dir / "rating_sentiment_correlation.csv", index=False, encoding="utf-8-sig")

    plot_rating_sentiment_boxplot(df, out_dir)
    plot_rating_sentiment_regression(df, out_dir)

    print(result.to_string(index=False))
    print(f"Saved results to {out_dir}")


if __name__ == "__main__":
    main()
