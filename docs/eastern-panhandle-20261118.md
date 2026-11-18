# Eastern Panhandle offshore expansion

Adds two NOAA GFS-Wave targets without changing the existing nine targets or the legacy five-area Worker:

- St. Marks offshore target: 29.95, -84.18. Validated actual ocean cell: 30.0000, -84.1666.
- Panacea offshore target: 29.90, -84.38. Validated actual ocean cell: 29.8333, -84.3333.

The initial validation decodes the actual NOAA NOMADS global.0p16 GRIB cycle 2026-11-18 06Z at every native three-hour forecast step +3 through +36, for both targets. All fields for an hour use the same significant-wave-height-valid ocean cell, and each target must retain that cell across hours. Missing swell remains null, never zero or a substitute cell.

The existing every-three-hour publisher now validates all eleven targets before publication. Initial eastern files may carry a newer cycle than unchanged existing files; every location file retains its own authoritative model cycle. No source timestamp is invented.

The isolated `coast-pilot-panhandle-preview` service uses `src/panhandle_preview.js` plus `src/panhandle_lookup.js`. The production legacy `tidemoon-wave-data` Worker is unchanged. For queries east of longitude -84.5 the nearest verified cell must be within 30 km; western lookup behavior is preserved. A selected index point must match every forecast row. Every response distance is measured from the actual requested coordinates, not the publisher's original offshore target.

Forecasts are regional offshore numerical guidance, not local breaking surf, harbor observations, safe-navigation advice or a surveyed coverage polygon. Inland and distant places must not be presented as locally measured waves.

Checks: Python unittest discovery; Node lookup tests; live endpoint tests for all original nine regions, Panacea, St. Marks town and river entrance; distant and invalid-coordinate rejection. App eligibility remains a separate client responsibility.
