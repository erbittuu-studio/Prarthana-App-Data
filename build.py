#!/usr/bin/env python3
"""
Data Builder Script
==================
Generates ZIP bundles and manifest.json from source content.

Usage:
    python build.py [--clean] [--verify] [--verbose]

Options:
    --clean     Remove build directory before building
    --verify    Verify existing build integrity
    --verbose   Show detailed output

Directory Structure:
    index.json          - Source of truth: app info, items metadata, versioning
    source/             - Content files (edit these)
        {item_id}/
            {item_id}_{lang}.json    - Content in each language
            {item_id}_meanings.json  - Meanings/explanations (optional)
            {item_id}.mp3            - Audio file (optional)

    build/              - Generated output (deploy this to GitHub)
        manifest.json   - Final manifest with checksums and file info
        texts/
            {item_id}.zip   - ZIP bundles for each item

Workflow:
    1. Edit index.json to add/update items (metadata, names, descriptions)
    2. Add content files in source/{item_id}/
    3. Run: python build.py
    4. Deploy build/ directory contents to GitHub data repository
"""

import os
import sys
import json
import hashlib
import zipfile
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Constants
SCRIPT_DIR = Path(__file__).parent
SOURCE_DIR = SCRIPT_DIR / "source"
BUILD_DIR = SCRIPT_DIR / "build"
INDEX_FILE = SCRIPT_DIR / "index.json"
TEXTS_DIR = BUILD_DIR / "texts"

AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav", ".aac"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def log(message: str, verbose: bool = True):
    """Print log message if verbose mode is on."""
    if verbose:
        print(f"  {message}")


def log_section(title: str):
    """Print section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def log_success(message: str):
    """Print success message."""
    print(f"  [OK] {message}")


def log_error(message: str):
    """Print error message."""
    print(f"  [ERROR] {message}")


def log_warning(message: str):
    """Print warning message."""
    print(f"  [WARN] {message}")


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compute_file_size(file_path: Path) -> int:
    """Get file size in bytes."""
    return file_path.stat().st_size


def load_json(file_path: Path) -> Optional[Dict]:
    """Load JSON file, return None if failed."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        log_error(f"Failed to load {file_path}: {e}")
        return None


def save_json(file_path: Path, data: Dict, indent: int = 2):
    """Save data to JSON file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def load_index() -> Optional[Dict]:
    """Load index.json - the source of truth."""
    if not INDEX_FILE.exists():
        log_error(f"index.json not found at {INDEX_FILE}")
        log_error("Create index.json with app info and items metadata")
        return None

    index = load_json(INDEX_FILE)
    if not index:
        return None

    # Validate required fields
    required = ["app", "data", "config", "languages", "items"]
    for field in required:
        if field not in index:
            log_error(f"Missing required field '{field}' in index.json")
            return None

    return index


def analyze_item_files(item_id: str, verbose: bool = False) -> Optional[Dict]:
    """Scan source folder to find content files for an item."""
    item_dir = SOURCE_DIR / item_id

    if not item_dir.exists():
        log_error(f"Source folder not found: {item_dir}")
        return None

    # Discover content files by language
    content_files: Dict[str, str] = {}
    for file in item_dir.iterdir():
        if file.suffix == ".json" and not file.name.endswith("_meanings.json"):
            # Parse language from filename: {item_id}_{lang}.json
            name = file.stem
            if name.startswith(f"{item_id}_"):
                lang = name[len(f"{item_id}_"):]
                if lang in ["en", "hi", "gu"]:
                    content_files[lang] = file.name
                    log(f"  Found content: {file.name} ({lang})", verbose)

    if not content_files:
        log_error(f"No content files found for {item_id}")
        return None

    # Check for meanings file
    meanings_file = item_dir / f"{item_id}_meanings.json"
    has_meanings = meanings_file.exists()
    if has_meanings:
        log(f"  Found meanings: {meanings_file.name}", verbose)

    # Check for audio file
    audio_file = None
    for ext in AUDIO_EXTENSIONS:
        potential_audio = item_dir / f"{item_id}{ext}"
        if potential_audio.exists():
            audio_file = potential_audio.name
            log(f"  Found audio: {audio_file}", verbose)
            break

    # Check for image file
    image_file = None
    for ext in IMAGE_EXTENSIONS:
        potential_image = item_dir / f"{item_id}{ext}"
        if potential_image.exists():
            image_file = potential_image.name
            log(f"  Found image: {image_file}", verbose)
            break

    return {
        "content": content_files,
        "meanings": meanings_file.name if has_meanings else None,
        "audio": audio_file,
        "image": image_file,
        "languages": list(content_files.keys()),
        "hasAudio": audio_file is not None,
        "hasMeanings": has_meanings,
        "hasImage": image_file is not None
    }


def create_index_json(item_id: str, files: Dict) -> Dict:
    """Create index.json content for a ZIP bundle."""
    index = {
        "id": item_id,
        "files": {
            "content": files["content"]
        }
    }

    if files["meanings"]:
        index["files"]["meanings"] = files["meanings"]

    if files["audio"]:
        index["files"]["audio"] = files["audio"]

    if files["image"]:
        index["files"]["image"] = files["image"]

    return index


def create_zip_bundle(item_id: str, files: Dict, verbose: bool = False) -> Optional[Path]:
    """Create ZIP bundle for an item."""
    item_dir = SOURCE_DIR / item_id
    zip_path = TEXTS_DIR / f"{item_id}.zip"

    # Ensure output directory exists
    TEXTS_DIR.mkdir(parents=True, exist_ok=True)

    # Create index.json for the bundle
    index_content = create_index_json(item_id, files)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add index.json
            index_json = json.dumps(index_content, ensure_ascii=False, indent=2)
            zf.writestr(f"{item_id}/index.json", index_json)
            log(f"  Added: {item_id}/index.json", verbose)

            # Add content files
            for lang, filename in files["content"].items():
                src_path = item_dir / filename
                if src_path.exists():
                    zf.write(src_path, f"{item_id}/{filename}")
                    log(f"  Added: {item_id}/{filename}", verbose)

            # Add meanings file
            if files["meanings"]:
                src_path = item_dir / files["meanings"]
                if src_path.exists():
                    zf.write(src_path, f"{item_id}/{files['meanings']}")
                    log(f"  Added: {item_id}/{files['meanings']}", verbose)

            # Add audio file
            if files["audio"]:
                src_path = item_dir / files["audio"]
                if src_path.exists():
                    zf.write(src_path, f"{item_id}/{files['audio']}")
                    log(f"  Added: {item_id}/{files['audio']}", verbose)

            # Add image file
            if files["image"]:
                src_path = item_dir / files["image"]
                if src_path.exists():
                    zf.write(src_path, f"{item_id}/{files['image']}")
                    log(f"  Added: {item_id}/{files['image']}", verbose)

        log_success(f"Created {zip_path.name}")
        return zip_path

    except Exception as e:
        log_error(f"Failed to create ZIP for {item_id}: {e}")
        return None


def create_manifest_item(item_meta: Dict, files: Dict, zip_path: Path) -> Dict:
    """Create manifest entry for an item with checksum."""
    checksum = compute_sha256(zip_path)
    size = compute_file_size(zip_path)
    item_id = item_meta["id"]

    return {
        "id": item_id,
        "name": item_meta.get("name", {"en": item_id}),
        "description": item_meta.get("description", {"en": ""}),
        "path": f"texts/{item_id}/index.json",
        "bundle": f"texts/{item_id}.zip",
        "languages": files["languages"],
        "hasAudio": files["hasAudio"],
        "hasMeanings": files["hasMeanings"],
        "hasImage": files["hasImage"],
        "checksum": checksum,
        "size": size
    }


def create_manifest(index: Dict, items: List[Dict]) -> Dict:
    """Create the complete manifest.json."""
    manifest = {
        "app": index["app"],
        "data": index["data"],
        "config": index["config"],
        "languages": index["languages"],
        "items": items,
        "_meta": {
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "generator": "build.py",
            "itemCount": len(items)
        }
    }
    return manifest


def verify_build(verbose: bool = False) -> bool:
    """Verify integrity of existing build."""
    log_section("Verifying Build Integrity")

    manifest_path = BUILD_DIR / "manifest.json"
    if not manifest_path.exists():
        log_error("manifest.json not found in build directory")
        return False

    manifest = load_json(manifest_path)
    if not manifest:
        return False

    all_valid = True
    for item in manifest.get("items", []):
        item_id = item["id"]
        expected_checksum = item.get("checksum")
        zip_path = BUILD_DIR / item["bundle"]

        if not zip_path.exists():
            log_error(f"{item_id}: ZIP file missing")
            all_valid = False
            continue

        if expected_checksum:
            actual_checksum = compute_sha256(zip_path)
            if actual_checksum == expected_checksum:
                log_success(f"{item_id}: Checksum valid")
            else:
                log_error(f"{item_id}: Checksum mismatch!")
                log(f"  Expected: {expected_checksum}", verbose)
                log(f"  Actual:   {actual_checksum}", verbose)
                all_valid = False
        else:
            log_warning(f"{item_id}: No checksum in manifest")

    return all_valid


def clean_build():
    """Remove build directory."""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        log_success(f"Removed {BUILD_DIR}")


def build(verbose: bool = False) -> bool:
    """Main build process."""
    log_section("Loading Index")
    index = load_index()
    if not index:
        return False

    log_success(f"Content version: {index['data']['contentVersion']}")
    log_success(f"Items defined: {len(index['items'])}")

    log_section("Processing Items")
    manifest_items = []
    errors = []

    for item_meta in index["items"]:
        item_id = item_meta["id"]
        log(f"\nProcessing: {item_id}", True)

        # Scan source folder for files
        files = analyze_item_files(item_id, verbose)
        if not files:
            errors.append(item_id)
            continue

        log_success(f"{item_id}: {len(files['languages'])} langs, audio={files['hasAudio']}, meanings={files['hasMeanings']}, image={files['hasImage']}")

        # Create ZIP bundle
        zip_path = create_zip_bundle(item_id, files, verbose)
        if not zip_path:
            errors.append(item_id)
            continue

        # Create manifest entry
        manifest_item = create_manifest_item(item_meta, files, zip_path)
        manifest_items.append(manifest_item)

    if errors:
        log_section("Errors")
        for item_id in errors:
            log_error(f"Failed to build: {item_id}")

    log_section("Creating Manifest")
    manifest = create_manifest(index, manifest_items)
    manifest_path = BUILD_DIR / "manifest.json"
    save_json(manifest_path, manifest)
    log_success(f"Created manifest.json with {len(manifest_items)} items")

    log_section("Build Summary")
    print(f"""
    Source:           {INDEX_FILE}
    Content Folder:   {SOURCE_DIR}
    Build Output:     {BUILD_DIR}

    Items Defined:    {len(index['items'])}
    Items Built:      {len(manifest_items)}
    Content Version:  {index['data']['contentVersion']}

    Files Generated:
      - manifest.json
      - texts/*.zip ({len(manifest_items)} files)

    Deploy the 'build/' directory contents to your GitHub data repository.
    """)

    return len(errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Build data bundles and manifest for DataFetcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--clean", action="store_true", help="Clean build directory before building")
    parser.add_argument("--verify", action="store_true", help="Verify existing build integrity")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("  Data Builder")
    print("="*60)

    if args.verify:
        success = verify_build(args.verbose)
        sys.exit(0 if success else 1)

    if args.clean:
        log_section("Cleaning Build Directory")
        clean_build()

    success = build(args.verbose)

    if success:
        log_section("Verifying Build")
        verify_build(args.verbose)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
