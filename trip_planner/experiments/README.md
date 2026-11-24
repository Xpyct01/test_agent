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

The DVC remote `minio` is the bucket `dvc` in the MinIO of the root `docker-compose.yml`, at
`http://localhost:9090` (`.dvc/config`). The bucket is created when MinIO starts. Credentials are kept out
of git in `.dvc/config.local`; set them once per clone (the values below are the compose defaults, use
`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` if you changed them in `.env`):

```powershell
docker compose up -d minio
uv sync --group experiments
uv run --group experiments dvc remote modify --local minio access_key_id minio
uv run --group experiments dvc remote modify --local minio secret_access_key miniosecret
uv run --group experiments dvc pull
```

After a run that changed data: `dvc add` the dataset folder, commit its `.dvc` file, then `dvc push`.
The remote lives in the `langfuse_minio_data` volume, so `docker compose down -v` deletes it too.
