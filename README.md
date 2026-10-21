# Tide & Moon — Phase 6 NOAA forecast delivery pilot

## Design / cost

Proof-of-concept delivery path: NOAA NOMADS GRIB2 → GitHub Actions (Python/ecCodes) → static JSON on GitHub Pages → Android HTTP downloader. The public NOAA output is public; **do not upload paid/private app source, credentials or private location data to this repository**. Public repositories on GitHub-hosted standard runners have free Actions usage under current GitHub billing rules; this is **not a guarantee of future zero cost or uptime**. GitHub Pages and Actions may have separate usage/abuse limitations. No account or hosting has been set up by ChatGPT.

## Setup

1. Create a separate **public** GitHub repository solely for these NOAA converter scripts (not the Tide & Moon app). Copy the contents of this folder to the repository root, including the hidden `.github/workflows/noaa-wave.yml` folder. Never upload your Android app to that public repo.
2. In repository **Settings → Pages**, set **Build and deployment → Source: GitHub Actions**.
3. From **Actions → Publish NOAA wave JSON → Run workflow**, manually trigger a first run. Check job logs before relying on results. Scheduled runs are best-effort and can be delayed. The converter refuses to publish a partial/failed dataset.
4. Open `https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME/index.json` and e.g. `/sandiego.json` (actual deployment URL is shown in the Actions deploy step). Confirm realistic values and timestamps.
5. Send back the Pages URL and the Actions log outcome for review. Android has not been connected, and no Build 4.43 is claimed.

## What this pilot proves / does not prove

- Publishes a **small fixed set of 5 offshore reference locations** and +3,+6,+9,+12 forecast hours, using nearest shared valid ocean grid point. No interpolation and no substitution across grid points.
- `null` signifies absent value, *not zero*. Three swell partitions may be absent. Directions are degrees true but direction *from/to* convention needs validation before compass UI.
- The cycle is chosen using current UTC minus 2 hours. If NOAA has not released the selected cycle, the workflow fails rather than publishing inaccurate data. Previously deployed files **remain visible but may be stale**, so Android must reject old timestamps. Staleness validation is not yet implemented in Android.
- **This is not nationwide dynamic-user-location coverage.** Static per-region JSON is only a hosting feasibility test. Nationwide service architecture, forecast horizon, rate limits, attribution, and licensing need further assessment.
- GitHub scheduled workflows can be delayed or disabled after 60 days of inactivity in public repositories. GitHub Pages also isn't necessarily suitable as a production API / high-volume content distribution system; check GitHub acceptable use and limits before commercialization.
- NOAA requests are serialized with a **10.5 second delay** to comply with NOAA's request for at least 10 seconds between scripted fetches. 5 regions × 4 hours = 20 files ~3.5 minutes minimum, plus startup.
- Not a safe-navigation, coastal inlet or in-harbor forecast. The model is offshore and represents coarse grid cells.

## Local code-only validation

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

No live NOAA downloads occur during unit tests. To generate a real publication on a machine with `eccodes` installed:

```bash
python publish_forecasts.py --output site --pause 10.5
```

Look for `site/index.json`, `site/carrabelle.json`, `site/boston.json`, `site/charleston.json`, `site/sandiego.json`, `site/galveston.json`. These only exist after successful NOAA downloads. Don't fabricate live test data.
