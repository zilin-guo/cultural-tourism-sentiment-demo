import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/{place_name}"

# Field masks keep API responses focused and reduce unnecessary billed fields.
TEXT_SEARCH_FIELDS = ",".join(
    [
        "nextPageToken",
        "places.name",
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.types",
        "places.rating",
        "places.userRatingCount",
    ]
)

DETAIL_FIELDS = ",".join(
    [
        "id",
        "name",
        "displayName",
        "formattedAddress",
        "types",
        "rating",
        "userRatingCount",
        "reviews.rating",
        "reviews.text",
        "reviews.publishTime",
        "reviews.relativePublishTimeDescription",
    ]
)


def log(message):
    encoding = sys.stdout.encoding or "utf-8"
    safe_message = str(message).encode(encoding, errors="replace").decode(encoding)
    print(safe_message)


def request_json(url, api_key, *, method="GET", payload=None, field_mask=None, retries=3):
    data = None
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
    }
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    last_error = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code} from Google Places API: {body}")
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == retries:
                raise
        time.sleep(2 * attempt)

    raise last_error


def text_search(api_key, query, max_results, sleep_seconds, region_code, language_code):
    places = []
    page_token = None

    while len(places) < max_results:
        payload = {
            "textQuery": query,
            "pageSize": min(max_results - len(places), 20),
            "languageCode": language_code,
            "regionCode": region_code,
        }
        if page_token:
            payload["pageToken"] = page_token

        data = request_json(
            TEXT_SEARCH_URL,
            api_key,
            method="POST",
            payload=payload,
            field_mask=TEXT_SEARCH_FIELDS,
        )
        batch = data.get("places", [])
        places.extend(batch)
        page_token = data.get("nextPageToken")

        if not page_token or not batch:
            break
        time.sleep(max(sleep_seconds, 2.0))

    return places[:max_results]


def place_details(api_key, place_name):
    return request_json(
        DETAILS_URL.format(place_name=place_name),
        api_key,
        field_mask=DETAIL_FIELDS,
    )


def text_value(value):
    if isinstance(value, dict):
        return value.get("text", "")
    return value or ""


def flatten_place(region, search_keyword, place):
    return {
        "region": region,
        "search_keyword": search_keyword,
        "place_resource_name": place.get("name", ""),
        "place_id": place.get("id", ""),
        "place_name": text_value(place.get("displayName")),
        "address": place.get("formattedAddress", ""),
        "rating": place.get("rating", ""),
        "user_rating_count": place.get("userRatingCount", ""),
        "place_types": "|".join(place.get("types", [])),
    }


def flatten_reviews(place_row, place):
    rows = []
    for review_index, review in enumerate(place.get("reviews", []), start=1):
        text = review.get("text", {})
        rows.append(
            {
                **place_row,
                "review_index": review_index,
                "review_text": text.get("text", ""),
                "review_language": text.get("languageCode", ""),
                "review_rating": review.get("rating", ""),
                "review_publish_time": review.get("publishTime", ""),
                "review_relative_time": review.get("relativePublishTimeDescription", ""),
            }
        )
    return rows


def matches_address_filter(place, filters):
    # Keep results inside the intended region when broad text queries drift.
    if not filters:
        return True
    address = (place.get("formattedAddress") or "").lower()
    return any(item.lower() in address for item in filters)


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a small Google Places review sample for cultural tourism research."
    )
    parser.add_argument("--region", default="Navarra, Spain")
    parser.add_argument("--region-code", default="ES")
    parser.add_argument("--language-code", default="en")
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Text Search query. Repeat this option to use multiple queries.",
    )
    parser.add_argument(
        "--queries-file",
        default=None,
        help="Optional UTF-8 text file with one Text Search query per line.",
    )
    parser.add_argument("--max-places", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument(
        "--address-filter",
        action="append",
        default=None,
        help="Keep only places whose formatted address contains this text. Repeat for OR matching.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/google_places_navarra_test",
        help="Directory for places.csv, reviews.csv, and raw_details.json.",
    )
    args = parser.parse_args()
    queries = []
    if args.queries_file:
        queries.extend(
            line.strip()
            for line in Path(args.queries_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    if args.query:
        queries.extend(args.query)
    if not queries:
        queries = ["tourist attractions in Navarra Spain"]

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise SystemExit("Set GOOGLE_MAPS_API_KEY before running this script.")

    output_dir = Path(args.output_dir)
    seen_place_ids = set()
    place_candidates = []

    for query in queries:
        log(f"Searching: {query}")
        remaining = args.max_places - len(place_candidates)
        for place in text_search(
            api_key,
            query,
            remaining,
            args.sleep,
            args.region_code,
            args.language_code,
        ):
            if not matches_address_filter(place, args.address_filter):
                continue
            place_id = place.get("id")
            if not place_id or place_id in seen_place_ids:
                continue
            # Google place IDs are the deduplication key across overlapping queries.
            seen_place_ids.add(place_id)
            place_candidates.append((query, place))
            if len(place_candidates) >= args.max_places:
                break
        if len(place_candidates) >= args.max_places:
            break
        time.sleep(args.sleep)

    places_rows = []
    reviews_rows = []
    raw_details = []

    for index, (query, place) in enumerate(place_candidates, start=1):
        summary = flatten_place(args.region, query, place)
        log(f"[{index}/{len(place_candidates)}] Details: {summary['place_name']}")
        try:
            detail = place_details(api_key, place["name"])
        except Exception as exc:
            log(f"Skipped details for {summary['place_id']}: {exc}")
            continue
        merged_place = {**place, **detail}
        place_row = flatten_place(args.region, query, merged_place)
        places_rows.append(place_row)
        reviews_rows.extend(flatten_reviews(place_row, merged_place))
        raw_details.append(merged_place)
        time.sleep(args.sleep)

    place_fields = [
        "region",
        "search_keyword",
        "place_resource_name",
        "place_id",
        "place_name",
        "address",
        "rating",
        "user_rating_count",
        "place_types",
    ]
    review_fields = place_fields + [
        "review_index",
        "review_text",
        "review_language",
        "review_rating",
        "review_publish_time",
        "review_relative_time",
    ]

    write_csv(output_dir / "places.csv", places_rows, place_fields)
    write_csv(output_dir / "reviews.csv", reviews_rows, review_fields)
    (output_dir / "raw_details.json").write_text(
        json.dumps(raw_details, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log(f"Saved {len(places_rows)} places to {output_dir / 'places.csv'}")
    log(f"Saved {len(reviews_rows)} reviews to {output_dir / 'reviews.csv'}")


if __name__ == "__main__":
    main()
