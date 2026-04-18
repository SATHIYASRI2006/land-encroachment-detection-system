Realtime ingestion folder structure:

1. Put each manifest JSON into `backend/live_feed/inbox/`
2. Keep the image files either:
   - in the same `inbox/` folder, or
   - at an absolute path referenced by `source_path`

Supported years:
- `2021`
- `2022`
- `2023`
- `2024`

Manifest example:

```json
{
  "plot_id": "plot9",
  "lat": 13.1016,
  "lng": 80.2324,
  "location_name": "Madhavaram Canal Edge",
  "area": "Madhavaram",
  "survey_no": "S.No 14/2B",
  "owner_name": "Revenue Department",
  "village": "Madhavaram",
  "district": "Chennai",
  "operator_note": "Realtime feed from external satellite pipeline",
  "boundary_geojson": {
    "type": "Polygon",
    "coordinates": [
      [
        [80.2304, 13.0996],
        [80.2344, 13.0996],
        [80.2344, 13.1036],
        [80.2304, 13.1036],
        [80.2304, 13.0996]
      ]
    ]
  },
  "images": [
    { "year": 2021, "source_path": "plot9_2021.png" },
    { "year": 2022, "source_path": "plot9_2022.png" },
    { "year": 2023, "source_path": "plot9_2023.png" },
    { "year": 2024, "source_path": "plot9_2024.png" }
  ]
}
```

Processing behavior:
- backend scans the inbox every 30 seconds by default
- manifest is moved to `archive/` after success
- manifest is moved to `failed/` if processing fails
- plot is inserted/updated in database
- images are copied into `backend/static/data/`
- analysis runs automatically
- alerts and live dashboard updates follow automatically
