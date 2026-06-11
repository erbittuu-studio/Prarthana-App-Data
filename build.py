#!/usr/bin/env python3
"""
Data Builder Script
==================
Generates ZIP bundles and manifest.json from source content.

Usage:
    python build.py [options]

Options:
    --clean     Remove build directory before building
    --verify    Verify existing build integrity
    --verbose   Show detailed output
    --publish   Increment version and push to GitHub

Version Management:
    Single version number. When version changes, app clears cache and
    re-downloads all items. Uses checksums for smart downloading - only
    downloads ZIPs with changed checksums.

Directory Structure:
    index.json          - Source of truth: app info, items metadata, versioning
    source/             - Content files (edit these)
        {item_id}/
            {item_id}_{lang}.json    - Content in each language
            {item_id}_meanings.json  - Meanings/explanations (optional)
            {item_id}.mp3            - Audio file (optional)
            {item_id}.png            - Image file (optional)

    build/              - Generated output (deploy this to GitHub)
        manifest.json   - Final manifest with checksums and file info
        texts/
            {item_id}.zip   - ZIP bundles for each item

Workflow:
    1. Edit content files in source/{item_id}/
    2. Run: python build.py --publish
    3. Script builds, commits, and pushes to GitHub automatically

Examples:
    python build.py                   # Build only (no version bump)
    python build.py --publish         # Build, bump version, commit & push
    python build.py --clean --publish # Clean build with version bump & push
    python build.py --verify          # Verify build integrity
"""

import os
import sys
import json
import hashlib
import zipfile
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Constants
SCRIPT_DIR = Path(__file__).parent
SOURCE_DIR = SCRIPT_DIR / "source"
BUILD_DIR = SCRIPT_DIR / "build"
INDEX_FILE = SCRIPT_DIR / "index.json"
TEXTS_DIR = BUILD_DIR / "texts"
CATEGORIES_SRC_DIR = SOURCE_DIR / "categories"
CATEGORIES_BUILD_DIR = BUILD_DIR / "categories"

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


def format_size(size_bytes: int) -> str:
    """Format size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


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
    required = ["app", "data", "config", "items"]
    for field in required:
        if field not in index:
            log_error(f"Missing required field '{field}' in index.json")
            return None

    # Ensure version exists
    if "version" not in index["data"]:
        index["data"]["version"] = 1

    return index


def bump_version(index: Dict) -> int:
    """Increment version and save to index.json."""
    current = index["data"].get("version", 0)
    new_version = current + 1
    index["data"]["version"] = new_version
    save_json(INDEX_FILE, index)
    return new_version


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

        return zip_path

    except Exception as e:
        log_error(f"Failed to create ZIP for {item_id}: {e}")
        return None


def create_manifest_item(item_meta: Dict, files: Dict, zip_path: Path) -> Dict:
    """Create manifest entry for an item with checksum."""
    checksum = compute_sha256(zip_path)
    size = compute_file_size(zip_path)
    item_id = item_meta["id"]

    result = {
        "id": item_id,
        "name": item_meta.get("name", item_id),
        "description": item_meta.get("description", ""),
        "path": f"texts/{item_id}/index.json",
        "bundle": f"texts/{item_id}.zip",
        "languages": files["languages"],
        "hasAudio": files["hasAudio"],
        "hasMeanings": files["hasMeanings"],
        "hasImage": files["hasImage"],
        "checksum": checksum,
        "size": size
    }

    # Include optional fields if present
    if "readingTimeMinutes" in item_meta:
        result["readingTimeMinutes"] = item_meta["readingTimeMinutes"]
    if "tags" in item_meta:
        result["tags"] = item_meta["tags"]

    return result


def copy_category_images(categories: List[Dict], verbose: bool = False) -> List[Dict]:
    """Copy category images to build directory and return updated categories with paths."""
    if not CATEGORIES_SRC_DIR.exists():
        log_warning("No categories source folder found")
        return categories

    CATEGORIES_BUILD_DIR.mkdir(parents=True, exist_ok=True)

    updated_categories = []
    for category in categories:
        cat_copy = category.copy()
        if "image" in category:
            src_image = CATEGORIES_SRC_DIR / category["image"]
            if src_image.exists():
                dst_image = CATEGORIES_BUILD_DIR / category["image"]
                shutil.copy2(src_image, dst_image)
                cat_copy["image"] = f"categories/{category['image']}"
                log(f"  Copied: {category['image']}", verbose)
            else:
                log_warning(f"Category image not found: {src_image}")
                cat_copy.pop("image", None)
        updated_categories.append(cat_copy)

    return updated_categories


def create_manifest(index: Dict, items: List[Dict], verbose: bool = False) -> Dict:
    """Create the complete manifest.json."""
    manifest = {
        "app": index["app"],
        "data": index["data"],
        "config": index["config"],
        "items": items,
        "_meta": {
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "generator": "build.py",
            "itemCount": len(items)
        }
    }

    # Include categories if defined, with updated image paths
    if "categories" in index:
        manifest["categories"] = copy_category_images(index["categories"], verbose)

    # Include deities if defined
    if "deities" in index:
        manifest["deities"] = index["deities"]

    # Include todaysPrayer if defined
    if "todaysPrayer" in index:
        manifest["todaysPrayer"] = index["todaysPrayer"]

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


def run_git_command(args: List[str], cwd: Path = SCRIPT_DIR) -> tuple[bool, str]:
    """Run a git command and return success status and output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except Exception as e:
        return False, str(e)


def git_push(version: int) -> bool:
    """Commit and push changes to GitHub."""
    log_section("Pushing to GitHub")

    # Check if we're in a git repo
    success, _ = run_git_command(["rev-parse", "--git-dir"])
    if not success:
        log_error("Not a git repository")
        return False

    # Add build directory and index.json
    log("Adding files to git...")
    success, output = run_git_command(["add", "build/", "index.json"])
    if not success:
        log_error(f"Failed to add files: {output}")
        return False

    # Check if there are changes to commit
    success, output = run_git_command(["diff", "--cached", "--quiet"])
    if success:
        log_warning("No changes to commit")
        return True

    # Commit
    commit_msg = f"Data update v{version}"
    log(f"Committing: {commit_msg}")
    success, output = run_git_command(["commit", "-m", commit_msg])
    if not success:
        log_error(f"Failed to commit: {output}")
        return False
    log_success("Committed changes")

    # Push
    log("Pushing to remote...")
    success, output = run_git_command(["push"])
    if not success:
        log_error(f"Failed to push: {output}")
        return False
    log_success("Pushed to GitHub")

    return True


def build(verbose: bool = False) -> tuple[bool, Optional[Dict], List[Dict]]:
    """Main build process. Returns (success, index, manifest_items)."""
    log_section("Loading Index")
    index = load_index()
    if not index:
        return False, None, []

    log_success(f"Version: {index['data']['version']}")
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
    manifest = create_manifest(index, manifest_items, verbose)
    manifest_path = BUILD_DIR / "manifest.json"
    save_json(manifest_path, manifest)
    log_success(f"Created manifest.json with {len(manifest_items)} items")
    if "categories" in manifest:
        log_success(f"Included {len(manifest['categories'])} categories with images")

    return len(errors) == 0, index, manifest_items


def print_summary(index: Dict, manifest_items: List[Dict], pushed: bool = False):
    """Print build summary."""
    log_section("Build Summary")

    total_size = sum(item.get("size", 0) for item in manifest_items)

    print(f"""
    Version:          {index['data']['version']}
    Items Built:      {len(manifest_items)}
    Total Size:       {format_size(total_size)}

    Files Generated:
      - manifest.json
      - texts/*.zip ({len(manifest_items)} files)

    Items:""")

    for item in manifest_items:
        size_str = format_size(item.get("size", 0))
        checksum_short = item.get("checksum", "")[:12] + "..."
        print(f"      - {item['id']}: {size_str} [{checksum_short}]")

    if pushed:
        print(f"""
    Status: Published to GitHub (v{index['data']['version']})
    """)
    else:
        print("""
    Next Steps:
      Run with --publish to bump version, commit & push to GitHub
    """)


def main():
    parser = argparse.ArgumentParser(
        description="Build data bundles and manifest for DataFetcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--clean", action="store_true", help="Clean build directory before building")
    parser.add_argument("--verify", action="store_true", help="Verify existing build integrity")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--publish", action="store_true", help="Bump version, build, commit & push to GitHub")

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

    # Handle version bump
    if args.publish:
        log_section("Version Management")
        index = load_index()
        if index:
            new_version = bump_version(index)
            log_success(f"Version bumped to {new_version}")

    success, index, manifest_items = build(args.verbose)

    if success and index:
        log_section("Verifying Build")
        verify_build(args.verbose)

        pushed = False
        if args.publish:
            pushed = git_push(index['data']['version'])

        print_summary(index, manifest_items, pushed)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
