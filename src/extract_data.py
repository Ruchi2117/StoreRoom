"""Verify the official archive, then extract data without executing bundled code."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "HoloSelecta-FinalDataset-20200127T164214Z-001.zip"
EXPECTED_SHA256 = "4492e5f544a035cf4884626187ebf39ab5e703f71a3ff05733b6c11baf926afb"


def safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Archive path escapes destination: {name}")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "data/downloads" / ARCHIVE_NAME)
    args = parser.parse_args()
    with args.archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Original archive SHA-256 does not match Mendeley; refusing extraction")
    destination = ROOT / "data/raw/holoselecta"
    extracted, skipped = [], []
    with zipfile.ZipFile(args.archive) as archive:
        for info in archive.infolist():
            target = safe_target(destination, info.filename)
            if info.is_dir():
                continue
            # The source includes a pickle and Python file. Neither is needed.
            if target.suffix.lower() not in {".xml", ".jpg", ".jpeg", ".png", ".txt", ".md"}:
                skipped.append(info.filename)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(info.filename)
    report = {"sha256": digest, "extracted_count": len(extracted), "skipped": skipped}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/extraction.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
