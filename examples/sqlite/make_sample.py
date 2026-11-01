"""Create a tiny example database; refuse to overwrite any existing file."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3


def make_sample(path: Path) -> None:
    with path.open("xb"):
        pass
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE materials(id INTEGER PRIMARY KEY, name TEXT NOT NULL, density REAL);"
            "CREATE TABLE notes(id INTEGER PRIMARY KEY, text TEXT NOT NULL);"
        )
        connection.executemany("INSERT INTO materials VALUES(?,?,?)", [
            (1, "aluminium", 2.70), (2, "copper", 8.96), (3, "silicon", 2.33),
        ])
        connection.execute("INSERT INTO notes VALUES(?,?)", (1, "Illustrative data only; density in g/cm³."))
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    make_sample(args.output)
    print(f"Created {args.output.name}: 2 tables, 4 illustrative rows")


if __name__ == "__main__":
    main()
