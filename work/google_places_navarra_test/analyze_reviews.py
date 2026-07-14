import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


REGION_LABELS = {
    "Navarra, Spain": "Navarra",
    "Torino, Italy": "Torino",
}

SENTIMENT_ORDER = ["positive", "neutral", "negative"]
SENTIMENT_COLORS = {
    "positive": "#2f9e44",
    "neutral": "#6c757d",
    "negative": "#c92a2a",
}
REGION_COLORS = {
    "Navarra": "#1f77b4",
    "Torino": "#ff7f0e",
}


def clean_text(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    return value


def sentiment_label(compound):
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def keyword_pattern(term):
    escaped = re.escape(term.lower())
    if re.search(r"\W", term):
        return re.compile(escaped)
    return re.compile(rf"\b{escaped}\b")


def match_terms(text, terms):
    lowered = text.lower()
    matched = []
    for term in terms:
        if keyword_pattern(term).search(lowered):
            matched.append(term)
    return matched


def add_theme_columns(df, themes):
    # A review can match multiple themes.
    for theme, terms in themes.items():
        matched_col = f"{theme}_matched_terms"
        flag_col = f"theme_{theme}"
        df[matched_col] = df["review_text_clean"].apply(
            lambda text: "; ".join(match_terms(text, terms))
        )
        df[flag_col] = df[matched_col].astype(bool)

    theme_flag_cols = [f"theme_{theme}" for theme in themes]
    df["theme_count"] = df[theme_flag_cols].sum(axis=1)
    df["matched_themes"] = df.apply(
        lambda row: "; ".join(
            theme for theme in themes if row[f"theme_{theme}"]
        ),
        axis=1,
    )
    return df


def save_bar_labels(ax, fmt="{:.0f}", padding=2):
    for container in ax.containers:
        labels = []
        for value in container.datavalues:
            if pd.isna(value):
                labels.append("")
            else:
                labels.append(fmt.format(value))
        ax.bar_label(container, labels=labels, padding=padding, fontsize=9)


def plot_sentiment_by_region(df, out_dir):
    counts = (
        df.groupby(["region_short", "sentiment_label"])
        .size()
        .reset_index(name="count")
    )
    totals = counts.groupby("region_short")["count"].transform("sum")
    counts["percent"] = counts["count"] / totals * 100
    counts["sentiment_label"] = pd.Categorical(
        counts["sentiment_label"], SENTIMENT_ORDER, ordered=True
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=counts,
        x="region_short",
        y="percent",
        hue="sentiment_label",
        hue_order=SENTIMENT_ORDER,
        palette=SENTIMENT_COLORS,
        ax=ax,
    )
    ax.set_title("Sentiment distribution by region")
    ax.set_xlabel("")
    ax.set_ylabel("Share of reviews (%)")
    ax.set_ylim(0, max(100, counts["percent"].max() + 12))
    ax.legend(title="Sentiment", frameon=False)
    save_bar_labels(ax, "{:.1f}")
    fig.tight_layout()
    fig.savefig(out_dir / "sentiment_by_region.png", dpi=200)
    plt.close(fig)


def plot_rating_by_region(df, out_dir):
    plot_df = df.copy()
    plot_df["review_rating"] = pd.to_numeric(plot_df["review_rating"], errors="coerce")
    plot_df = plot_df.dropna(subset=["review_rating"])
    counts = (
        plot_df.groupby(["region_short", "review_rating"])
        .size()
        .reset_index(name="count")
    )
    counts["review_rating"] = counts["review_rating"].astype(int).astype(str)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=counts,
        x="review_rating",
        y="count",
        hue="region_short",
        palette=REGION_COLORS,
        ax=ax,
    )
    ax.set_title("Google review rating distribution")
    ax.set_xlabel("Review rating")
    ax.set_ylabel("Number of reviews")
    ax.legend(title="Region", frameon=False)
    save_bar_labels(ax, "{:.0f}")
    fig.tight_layout()
    fig.savefig(out_dir / "rating_distribution_by_region.png", dpi=200)
    plt.close(fig)


def plot_theme_frequency(theme_summary, out_dir):
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=theme_summary,
        y="theme_label",
        x="review_share_percent",
        hue="region_short",
        palette=REGION_COLORS,
        ax=ax,
    )
    ax.set_title("Theme frequency by region")
    ax.set_xlabel("Share of reviews mentioning theme (%)")
    ax.set_ylabel("")
    ax.legend(title="Region", frameon=False)
    save_bar_labels(ax, "{:.1f}", padding=3)
    fig.tight_layout()
    fig.savefig(out_dir / "theme_frequency_by_region.png", dpi=200)
    plt.close(fig)


def plot_average_sentiment_by_theme(theme_summary, out_dir):
    fig, ax = plt.subplots(figsize=(10, 6.4))
    sns.barplot(
        data=theme_summary,
        y="theme_label",
        x="avg_sentiment_compound",
        hue="region_short",
        palette=REGION_COLORS,
        ax=ax,
    )
    ax.axvline(0, color="#343a40", linewidth=1)
    ax.set_title("Average VADER sentiment by theme")
    ax.set_xlabel("Average compound sentiment score")
    ax.set_ylabel("")
    handles, labels = ax.get_legend_handles_labels()
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
    fig.savefig(out_dir / "average_sentiment_by_theme.png", dpi=200)
    plt.close(fig)


def plot_compound_distribution(df, out_dir):
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.kdeplot(
        data=df,
        x="sentiment_compound",
        hue="region_short",
        common_norm=False,
        fill=True,
        alpha=0.25,
        palette=REGION_COLORS,
        ax=ax,
    )
    ax.axvline(0.05, color="#2f9e44", linewidth=1, linestyle="--")
    ax.axvline(-0.05, color="#c92a2a", linewidth=1, linestyle="--")
    ax.set_title("Sentiment score distribution")
    ax.set_xlabel("VADER compound score")
    ax.set_ylabel("Density")
    fig.tight_layout()
    fig.savefig(out_dir / "sentiment_score_distribution.png", dpi=200)
    plt.close(fig)


def build_theme_summary(df, themes):
    rows = []
    region_counts = df.groupby("region_short").size().to_dict()
    for region_short, region_df in df.groupby("region_short"):
        for theme in themes:
            flag_col = f"theme_{theme}"
            matched = region_df[region_df[flag_col]]
            count = len(matched)
            rows.append(
                {
                    "region_short": region_short,
                    "theme": theme,
                    "theme_label": theme.replace("_", " ").title(),
                    "review_count": count,
                    "total_reviews_region": region_counts[region_short],
                    "review_share_percent": round(count / region_counts[region_short] * 100, 2),
                    "avg_sentiment_compound": round(matched["sentiment_compound"].mean(), 4)
                    if count
                    else 0,
                    "negative_review_count": int((matched["sentiment_label"] == "negative").sum()),
                }
            )
    return pd.DataFrame(rows)


def write_summary_tables(df, theme_summary, out_dir):
    summary = (
        df.groupby("region_short")
        .agg(
            reviews=("review_text_clean", "count"),
            unique_places=("place_id", "nunique"),
            avg_google_review_rating=("review_rating_numeric", "mean"),
            avg_place_rating=("place_rating_numeric", "mean"),
            avg_sentiment_compound=("sentiment_compound", "mean"),
            positive_share=("sentiment_label", lambda x: (x == "positive").mean() * 100),
            neutral_share=("sentiment_label", lambda x: (x == "neutral").mean() * 100),
            negative_share=("sentiment_label", lambda x: (x == "negative").mean() * 100),
            theme_mention_share=("theme_count", lambda x: (x > 0).mean() * 100),
        )
        .round(3)
        .reset_index()
    )
    summary.to_csv(out_dir / "summary_metrics.csv", index=False, encoding="utf-8-sig")

    language_summary = (
        df.groupby(["region_short", "review_language"])
        .size()
        .reset_index(name="review_count")
        .sort_values(["region_short", "review_count"], ascending=[True, False])
    )
    language_summary.to_csv(out_dir / "language_summary.csv", index=False, encoding="utf-8-sig")

    sentiment_counts = (
        df.groupby(["region_short", "sentiment_label"])
        .size()
        .reset_index(name="review_count")
    )
    sentiment_counts.to_csv(out_dir / "sentiment_counts.csv", index=False, encoding="utf-8-sig")
    theme_summary.to_csv(out_dir / "theme_summary.csv", index=False, encoding="utf-8-sig")

    negative_examples = (
        df[df["sentiment_label"] == "negative"]
        .sort_values(["region_short", "sentiment_compound"])
        [
            [
                "region_short",
                "place_name",
                "review_rating",
                "sentiment_compound",
                "matched_themes",
                "review_text_clean",
            ]
        ]
        .head(30)
    )
    negative_examples.to_csv(out_dir / "negative_review_examples.csv", index=False, encoding="utf-8-sig")


def main():
    parser = argparse.ArgumentParser(
        description="Run VADER sentiment analysis and keyword theme coding on Google Places reviews."
    )
    parser.add_argument(
        "--input",
        default="outputs/google_places_navarra_torino_combined/reviews_1000_balanced.csv",
    )
    parser.add_argument(
        "--themes",
        default="work/google_places_navarra_test/theme_keywords.json",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/google_places_navarra_torino_analysis",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    themes_path = Path(args.themes)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", font_scale=1.0)
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"

    df = pd.read_csv(input_path)
    themes = json.loads(themes_path.read_text(encoding="utf-8"))

    df["review_text_clean"] = df["review_text"].apply(clean_text)
    df = df[df["review_text_clean"].astype(bool)].copy()
    df = df.drop_duplicates(subset=["region", "place_id", "review_text_clean"]).copy()
    df["region_short"] = df["region"].map(REGION_LABELS).fillna(df["region"])
    df["review_rating_numeric"] = pd.to_numeric(df["review_rating"], errors="coerce")
    df["place_rating_numeric"] = pd.to_numeric(df["rating"], errors="coerce")

    analyzer = SentimentIntensityAnalyzer()
    # VADER returns negative, neutral, positive, and compound sentiment scores.
    scores = df["review_text_clean"].apply(analyzer.polarity_scores).apply(pd.Series)
    scores = scores.rename(
        columns={
            "neg": "sentiment_neg",
            "neu": "sentiment_neu",
            "pos": "sentiment_pos",
            "compound": "sentiment_compound",
        }
    )
    df = pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)
    df["sentiment_label"] = df["sentiment_compound"].apply(sentiment_label)

    df = add_theme_columns(df, themes)
    theme_summary = build_theme_summary(df, themes)

    df.to_csv(out_dir / "analyzed_reviews.csv", index=False, encoding="utf-8-sig")
    write_summary_tables(df, theme_summary, out_dir)

    plot_sentiment_by_region(df, out_dir)
    plot_rating_by_region(df, out_dir)
    plot_theme_frequency(theme_summary, out_dir)
    plot_average_sentiment_by_theme(theme_summary, out_dir)
    plot_compound_distribution(df, out_dir)

    print(f"Analyzed reviews: {len(df)}")
    print(f"Unique places: {df['place_id'].nunique()}")
    print(f"Output directory: {out_dir}")


if __name__ == "__main__":
    main()
