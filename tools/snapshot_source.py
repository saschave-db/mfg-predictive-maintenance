"""Copy the deployed pipeline + shared feature/physics source into evidence/source_snapshot/ (byte-identical)
and write SHA256SUMS. Run with --check to verify the snapshot still matches src/.

The E09 evidence notebook re-computes these hashes on the files the bundle deployed to the workspace.
"""
import hashlib
import shutil
import sys
from pathlib import Path

FILES = sorted([*Path("src/pipeline").glob("*.py"), *Path("src/pdm").glob("*.py"),
                Path("src/simulator/zerobus_producer.py"), Path("resources/pipeline.yml")])
OUT = Path("evidence/source_snapshot")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


if "--check" in sys.argv:
    bad = [f for f in FILES if sha(f) != sha(OUT / f)]
    print("snapshot matches src" if not bad else f"MISMATCH: {bad}")
    sys.exit(1 if bad else 0)

if OUT.exists():
    shutil.rmtree(OUT)
lines = []
for f in FILES:
    (OUT / f).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(f, OUT / f)
    lines.append(f"{sha(f)}  {f}")
(OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
