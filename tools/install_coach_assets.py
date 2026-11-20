"""Safely install the versioned 小奶茶 bone-rig PNG archive into JabJam.

Usage:
  python3 tools/install_coach_assets.py /path/to/小奶茶_2D骨骼素材_接缝修正版_v0.1.zip --check
  python3 tools/install_coach_assets.py /path/to/小奶茶_2D骨骼素材_接缝修正版_v0.1.zip

No external dependencies. Requires the reviewed v0.1 ZIP, not a source music file.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from zipfile import ZipFile

EXPECTED_SHA256 = "9d280b993b8656c5993c6677923266ad2b7841168bd6192ea65dba2603959380"
EXPECTED_PARTS = 29
MAX_UNCOMPRESSED = 18 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT / "assets" / "coaches" / "milktea"


def validate(archive):
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    if checksum != EXPECTED_SHA256:
        raise ValueError(f"Unexpected ZIP SHA-256: {checksum}. Expected {EXPECTED_SHA256}; refusing unreviewed artwork")
    with ZipFile(archive) as package:
        files = [i for i in package.infolist() if not i.is_dir()]
        names = [i.filename for i in files]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate names in the artwork archive")
        for entry in files:
            posix = PurePosixPath(entry.filename)
            if posix.is_absolute() or ".." in posix.parts or "\\" in entry.filename:
                raise ValueError(f"Unsafe archive path: {entry.filename}")
            if entry.file_size > MAX_UNCOMPRESSED:
                raise ValueError(f"Oversized archive entry: {entry.filename}")
        if sum(x.file_size for x in files) > MAX_UNCOMPRESSED:
            raise ValueError("Coach archive exceeds unpacked size limit")
        pngs = [name for name in names if name.startswith("parts/") and name.endswith(".png")]
        if len(pngs) != EXPECTED_PARTS or "rig_manifest.json" not in names:
            raise ValueError(f"Expected {EXPECTED_PARTS} part PNGs and rig_manifest.json")
        manifest = json.loads(package.read("rig_manifest.json"))
        if manifest.get("schema") != "jabjam-coach-cutout-v1":
            raise ValueError("Unexpected rig manifest version")
        referenced = {part["file"] for part in manifest["parts"].values()}
        if referenced != set(pngs):
            raise ValueError("Rig manifest and 29 PNGs do not agree")
        for name in pngs:
            with package.open(name) as png:
                if png.read(8) != PNG_SIGNATURE:
                    raise ValueError(f"Invalid PNG signature: {name}")
    return names


def install(archive, dest):
    names = validate(archive)
    if dest.exists():
        raise FileExistsError(f"Refusing to overwrite existing skin: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".milktea-staging-", dir=dest.parent))
    try:
        with ZipFile(archive) as package:
            for name in names:
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(name) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
        stage.rename(dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(f"Installed {EXPECTED_PARTS} separate PNGs and rig manifest into {dest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate only; do not write anything")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Override installation folder")
    args = parser.parse_args()
    if args.check:
        print(f"Verified: {len(validate(args.archive))} archive files, {EXPECTED_PARTS} PNG rig parts")
    else:
        install(args.archive, args.dest)


if __name__ == "__main__":
    main()
