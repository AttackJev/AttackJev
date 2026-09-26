"""Reassemble the evidence archive, extract it and verify every file against its SHA-256.

Offline, standard library only. Output: evidence/restored/ (git-ignored).
  python evidence/restore_and_verify.py [--output PATH]
"""
import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=HERE / "restored")
    a = ap.parse_args()
    idx = json.loads((HERE / "archive-index.json").read_text())
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "evidence.tar.xz"
        with archive.open("wb") as out:
            for part in idx["parts"]:
                f = HERE / part["file"]
                assert f.stat().st_size == part["bytes"] and sha(f) == part["sha256"], part["file"]
                out.write(f.read_bytes())
        assert sha(archive) == idx["archive_sha256"], "archive checksum mismatch"
        with tarfile.open(archive, "r:xz") as tf:
            for m in tf.getmembers():
                target = (a.output / m.name).resolve()
                assert target.is_relative_to(a.output.resolve()) and m.isfile()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tf.extractfile(m).read())
    manifest = json.loads((HERE / "evidence-files.json").read_text())
    for f in manifest:
        p = a.output / f["path"]
        assert p.stat().st_size == f["bytes"] and sha(p) == f["sha256"], f["path"]
    print(json.dumps({"verified_files": len(manifest), "output": str(a.output),
                      "evaluation_responses": idx["current_response_count"],
                      "rerun_responses": idx["repeat_response_count"]}, indent=1))


if __name__ == "__main__":
    main()
