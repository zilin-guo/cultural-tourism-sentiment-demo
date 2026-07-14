import csv
from pathlib import Path


ROOT = Path("outputs")
NAVARRA = ROOT / "google_places_navarra_200_filtered"
TORINO = ROOT / "google_places_torino_200_filtered"
OUT = ROOT / "google_places_navarra_torino_combined"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    navarra_places = read_csv(NAVARRA / "places.csv")
    torino_places = read_csv(TORINO / "places.csv")
    navarra_reviews = read_csv(NAVARRA / "reviews.csv")
    torino_reviews = read_csv(TORINO / "reviews.csv")

    combined_places = navarra_places + torino_places
    combined_reviews = navarra_reviews + torino_reviews

    # The balanced sample supports simple side-by-side comparison.
    balanced_reviews = navarra_reviews[:500] + torino_reviews[:500]

    write_csv(OUT / "places_combined.csv", combined_places, combined_places[0].keys())
    write_csv(OUT / "reviews_all.csv", combined_reviews, combined_reviews[0].keys())
    write_csv(OUT / "reviews_1000_balanced.csv", balanced_reviews, combined_reviews[0].keys())

    place_ids = [row["place_id"] for row in combined_places]
    review_place_ids = [row["place_id"] for row in combined_reviews]

    print(f"Navarra places: {len(navarra_places)}")
    print(f"Navarra reviews: {len(navarra_reviews)}")
    print(f"Torino places: {len(torino_places)}")
    print(f"Torino reviews: {len(torino_reviews)}")
    print(f"Combined places: {len(combined_places)}")
    print(f"Combined reviews: {len(combined_reviews)}")
    print(f"Balanced analysis reviews: {len(balanced_reviews)}")
    print(f"Duplicate place_id in places: {len(place_ids) - len(set(place_ids))}")
    print(f"Places represented in all reviews: {len(set(review_place_ids))}")


if __name__ == "__main__":
    main()
