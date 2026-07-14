# Google Places Review Collection

This script collects cultural tourism places and available Google Places reviews for a selected region.

## Google Cloud Setup

Enable this API in the same project as your API key:

- Places API (New)

If the script returns `SERVICE_DISABLED`, open the activation link from the error message, enable Places API (New), wait a few minutes, and run again.

## Run

PowerShell:

```powershell
$env:GOOGLE_MAPS_API_KEY = "YOUR_API_KEY"
python work\google_places_navarra_test\fetch_places_reviews.py --max-places 10
```

The script writes:

- `outputs/google_places_navarra_test/places.csv`
- `outputs/google_places_navarra_test/reviews.csv`
- `outputs/google_places_navarra_test/raw_details.json`

## Notes

- Google Places API returns at most 5 reviews per place.
- The default query is `tourist attractions in Navarra Spain`.
- For a larger sample, repeat `--query` with more cultural-tourism keywords and deduplicate by place ID.
