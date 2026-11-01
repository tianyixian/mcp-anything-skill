"""Deterministic process fixture; it is never used as scientific evidence."""

import json
import sys
import time
from pathlib import Path

mode = Path("input.in").read_text(encoding="utf-8").strip()
Path("engine-info.json").write_text(json.dumps({"backend": "test-fixture", "version": "fake"}), encoding="utf-8")
if mode == "sleep":
    print("started", flush=True)
    time.sleep(30)
elif mode == "flood":
    for _ in range(10000):
        print("x" * 4096, flush=True)
elif mode == "fail":
    print("intentional fixture failure", file=sys.stderr, flush=True)
    raise SystemExit(7)
else:
    print(
        "Created 32 atoms\nStep Temp PotEng KinEng TotEng Press Volume Density\n0 1 -2 1 -1 0 40 0.8\n10 1.1 -2.1 1.1 -1 0.1 40 0.8\nTotal wall time: 0:00:00",
        flush=True,
    )
