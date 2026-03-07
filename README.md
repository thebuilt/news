# Asbestos News Tracker (Zero Cost)

Static website + GitHub Actions pipeline that fetches daily asbestos-related news using:
- GDELT API
- Google News RSS

## What is stored
Only metadata is saved:
- title
- outlet
- source country
- date
- URL

No article body is stored.

## Features
- Daily update at 03:00 IST
- Rolling 7-day archive (older auto-deleted)
- Country-wise segmentation
- Clickable world map
- Dark/light theme toggle
- Loading progress bar

## Deploy on GitHub (manual)
1. Create repo named `news`.
2. Upload all files/folders from this project root.
3. Go to `Settings -> Actions -> General` and set workflow permissions to `Read and write permissions`.
4. Go to `Settings -> Pages`:
   - Source: Deploy from a branch
   - Branch: `main` and `/ (root)`
5. Add DNS CNAME:
   - Host: `news`
   - Value: `<your-github-username>.github.io`
6. In repo Actions tab, run workflow `Daily News Build` once manually.

## Notes
- Country mapping is source-country first.
- If a source country is unavailable, domain-TLD inference is used.
- Keyword expansion uses Wikidata labels/aliases for multilingual variants.
