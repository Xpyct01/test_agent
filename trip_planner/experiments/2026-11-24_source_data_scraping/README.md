# Source data scraping (2026-11-24)

**Question.** Can the two sources named in the task (the official Picos de Europa itinerary list
and an example hiking gear list) become clean CSV tables? The hand-written `trip_planner/data/trails.json`
and `equipment.json` could then be rebuilt from real data: lengths, ascents, durations, difficulty and safety
notes from the park itself.

**Method** (`scripts/scrape.py`).

- **Trails.** The scraper reads the index page
  <https://www.miteco.gob.es/es/parques-nacionales-oapn/red-parques-nacionales/parques-nacionales/picos-europa/guia-visitante/itinerarios.html>.
  It collects each trail link under the PR, GR and high-mountain sections, then reads every trail page.
  Each `<strong>Label</strong> (gloss): value` paragraph becomes a text column. Numbers are parsed from those
  texts: the **first** figure for length, ascent, descent and duration (usually the one-way or main variant),
  and the difficulty mapped to `easy/moderate/hard/very_hard`.
  Code: `shared/source_data/trails.py`.
- **Gear.** <https://australianhiker.com.au/gear/multiday-gear-list/>: one row per bold item label under a
  category heading from the page's table of contents, with the "why I chose this" bullets joined by ` | `.
  Code: `shared/source_data/gear.py`.
- Every downloaded page is kept under `data/<dataset>/raw/`, so parsing can be re-run offline and stays
  reproducible. Requests are retried (3 attempts, linear back-off) and spaced 1 s apart.
- No MLflow run: this step makes data and computes no metrics, and the repo has no
  `experiment_tracking` package yet.

## Conclusions

- **Trails: done.** `data/picos_trails/trails.csv` holds 31 trails: 25 PR, 2 GR and 4 high-mountain.
  Every trail has a length, a duration and a difficulty. Ascent and descent are missing where the page gives
  no elevation (PR-PNPE 26, GR-PNPE 202, PR-PNPE 29), or where only one direction is stated
  (for example PR-PNPE 11 lists only a descent).
- Difficulty: 13 easy, 12 moderate, 4 hard, 2 very hard.
- The first-figure rule is a simplification. PR-PNPE 3 (Cares) lists "3 h 20 min" and "5 h 30 min" for its
  21 km variant, and the parser keeps 3.33 h. The raw `*_text` columns are kept for such cases.
- **Gear: done.** `data/hiking_gear/gear_items.csv` holds 80 items in 13 categories: 66 core items and
  14 condition-dependent "swap outs". Every item has a product link and at least one reason. The live site
  answers scripted requests with a Cloudflare challenge (HTTP 403), so the source is the Internet Archive
  snapshot of 2025-11-16. Archive prefixes are stripped from the product links.
- Gear quirks kept as published: "Water Bladder" is its own heading on the page, so it is its own category.
  One product link points to the site's WordPress admin. A few links are Amazon short links.
- Not adopted into `app/` yet: `trip_planner/data/trails.json` is still hand-written.

## Results

| dataset | file | rows | columns |
|---|---|---|---|
| picos_trails | `data/picos_trails/trails.csv` | 31 | code, name, section, type, length_km, ascent_m, descent_m, duration_h, difficulty, the raw field texts, description, how-to, points of interest, precautions (es/en), map and profile PDF links, source URL |
| hiking_gear | `data/hiking_gear/gear_items.csv` | 80 | category, item_type, product, is_swap_out, reasons, product_url, source_url |

## Run

```powershell
uv sync --group experiments
dvc pull        # once a DVC remote is configured
uv run --group experiments python -m trip_planner.experiments.2026-11-24_source_data_scraping.scripts.scrape
```

A full online run takes about 1.5 min (33 pages); from the cached `raw/` pages it takes under 2 s.
`--sources trails|gear` picks one source, `--refresh` downloads the pages again, `--delay` sets the pause
between requests and `--gear-url` overrides the gear page (for example a newer snapshot).

Afterwards:

```powershell
dvc add trip_planner/experiments/data/picos_trails trip_planner/experiments/data/hiking_gear
git add trip_planner/experiments/data/*.dvc trip_planner/experiments/data/.gitignore
```
