# trip_planner experiments

Offline experiments and data preparation for the trip planner. Run every script as a module from the
repository root with `uv run --group experiments python -m trip_planner.experiments.<folder>.scripts.<step>`.
`app/` never imports this package.

## Experiments

| folder | question | status |
|---|---|---|
| [`2026-11-24_source_data_scraping`](2026-11-24_source_data_scraping/README.md) | Turn the task's trail and gear sources into CSV | done: 31 trails, 80 gear items |

## Shared code

| module | contents |
|---|---|
| `shared/utils/paths.py` | `DATA` and one constant per dataset folder |
| `shared/utils/files.py` | CSV read/write of dataclass rows |
| `shared/source_data/fetch.py` | `PageFetcher`: retrying, rate-limited HTTP with a raw-HTML cache |
| `shared/source_data/trails.py` | `PicosTrailScraper` and the Spanish field parsers (length, elevation, duration, difficulty) |
| `shared/source_data/gear.py` | `GearListScraper` for the Australian Hiker gear list |

## MLflow experiments

None yet: the scraping step logs no metrics.

## Data (DVC)

| dataset | `.dvc` file | made by | contents |
|---|---|---|---|
| `picos_trails` | `data/picos_trails.dvc` | `2026-11-24_source_data_scraping/scripts/scrape.py` | `trails.csv` and `raw/*.html` page snapshots |
| `hiking_gear` | `data/hiking_gear.dvc` | same | `gear_items.csv` and the archived page in `raw/` |

No DVC remote is configured yet (`dvc remote list` is empty), so the data exists only in the local DVC cache.
To share it, add a remote and push:

```powershell
dvc remote add -d storage <url>
dvc push
```
