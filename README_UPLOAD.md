# Tide & Moon — Cloudflare static-asset pilot

This contains **expired historical test forecasts from 2026-10-21**, for verifying Cloudflare downloads only. Never treat the values as current marine conditions. This package does NOT automate tile updates.

## Upload to the existing GitHub repository
1. Extract this ZIP locally.
2. In github.com/gr8polarbear2026/tidemoon-wave-data, choose **Add file > Upload files**.
3. Drag **the `public` folder** AND `wrangler.jsonc` together onto the upload screen (or drag the `public/wave` directory tree and separately upload `wrangler.jsonc`). Do not drag the ZIP itself.
4. Commit directly to `main`. The existing Python files and .github/workflows must remain untouched.
5. In Cloudflare Workers & Pages, resume Git repository creation for `tidemoon-wave-data`; leave Build command empty; deployment uses default `npx wrangler deploy` which reads `wrangler.jsonc`.
6. When deployed, test `https://<your-worker>.workers.dev/wave/index.json` and one `.json.gz` tile.

Check Cloudflare's displayed deployment build settings before clicking Deploy. The pilot is static-file serving only, not running the NOAA Python converter on Cloudflare.

The 43 tile SHA-256 hashes match the prior Phase 10 index. All 43 gzip payloads parse. This package is a deployment prototype, not a live forecast service.
