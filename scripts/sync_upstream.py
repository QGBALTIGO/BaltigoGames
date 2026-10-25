"""Install a pinned, self-contained copy of the MIT licensed upstream game assets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    version = json.loads((ROOT / "data/upstream-version.json").read_text(encoding="utf-8"))
    target = Path(args.output).resolve()
    target.mkdir(parents=True, exist_ok=True)
    marker = target / ".mirror-info.json"
    if marker.exists():
        installed = json.loads(marker.read_text())
        if installed.get("commit") == version["commit"] and installed.get("archive_sha256") == version["archive_sha256"]:
            print(json.dumps({"ready": True, "cached": True, **installed}), flush=True)
            return
        raise RuntimeError("use a separate directory for each source version")
    archive = target.parent / ("games-" + version["commit"] + ".tar.gz")
    if not archive.exists():
        temporary = archive.with_suffix(".download")
        url = f"https://codeload.github.com/{version['repository']}/tar.gz/{version['commit']}"
        count = 0
        with httpx.stream("GET", url, timeout=httpx.Timeout(300, connect=30), follow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as file:
                for chunk in response.iter_bytes(1024 * 1024):
                    file.write(chunk)
                    count += len(chunk)
                    if count % (50 * 1024 * 1024) < len(chunk):
                        print(json.dumps({"downloaded_mib": round(count / 1048576)}), flush=True)
        temporary.replace(archive)
    with archive.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    if digest != version["archive_sha256"]:
        raise RuntimeError("upstream archive does not match the reviewed SHA-256")
    count = 0
    with tarfile.open(archive, "r|gz") as source:
        for member in source:
            parts = PurePosixPath(member.name).parts[1:]
            if not parts:
                continue
            if member.issym() or member.islnk():
                raise RuntimeError("upstream archive contains a link")
            member.name = str(PurePosixPath(*parts))
            source.extract(member, target, filter="data")
            count += member.isfile()
    marker.write_text(json.dumps({**version, "files": count, "archive_sha256": digest}, indent=2), encoding="utf-8")
    print(json.dumps({"ready": True, "files": count, "commit": version["commit"], "archive_sha256": digest}), flush=True)


if __name__ == "__main__":
    main()
