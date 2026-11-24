"""Reading and writing of the experiment data files."""

import csv
import dataclasses
import pathlib
from collections.abc import Sequence
from typing import Any


def write_csv(path: pathlib.Path, rows: Sequence[Any]) -> None:
    """Writes dataclass rows to a UTF-8 CSV file with a header line.

    Args:
        path: Output file; its parent directory is created if missing.
        rows: Instances of one dataclass; its fields become the columns.

    Raises:
        ValueError: If `rows` is empty, so the columns are unknown.
    """
    if not rows:
        raise ValueError(f'No rows to write to {path}.')
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [field.name for field in dataclasses.fields(rows[0])]
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(dataclasses.asdict(row) for row in rows)


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    """Reads a CSV file with a header line into one dict per row."""
    with path.open(encoding='utf-8', newline='') as file:
        return list(csv.DictReader(file))
