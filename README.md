# Prarthana App Data

Content data for the Prarthana iOS application. This folder contains the source content files and build script to generate deployment-ready ZIP bundles.

## Directory Structure

```
Prarthana-App-Data/
├── index.json          # Source of truth: app info, items metadata
├── build.py            # Build script
├── source/             # Content files (edit these)
│   └── {item_id}/
│       ├── {item_id}_en.json       # English content
│       ├── {item_id}_hi.json       # Hindi content
│       ├── {item_id}_gu.json       # Gujarati content
│       ├── {item_id}_meanings.json # Meanings (optional)
│       ├── {item_id}.mp3           # Audio (optional)
│       └── {item_id}.png           # Image (optional)
└── build/              # Generated output (deploy to GitHub)
    ├── manifest.json   # Final manifest with checksums
    └── texts/
        └── {item_id}.zip
```

## Workflow

### 1. Add/Update Items in index.json

Edit `index.json` to add or update item metadata:

```json
{
  "items": [
    {
      "id": "item_id",
      "name": {
        "en": "English Name",
        "hi": "Hindi Name",
        "gu": "Gujarati Name"
      },
      "description": {
        "en": "English description",
        "hi": "Hindi description",
        "gu": "Gujarati description"
      }
    }
  ]
}
```

### 2. Add Content Files

Create a folder in `source/` with the item ID and add content files:

```
source/my_item/
├── my_item_en.json      # Required: English content
├── my_item_hi.json      # Optional: Hindi content
├── my_item_gu.json      # Optional: Gujarati content
├── my_item_meanings.json # Optional: Verse meanings
├── my_item.mp3          # Optional: Audio file
└── my_item.png          # Optional: Cover image
```

### 3. Run Build Script

```bash
# Build, bump version, commit & push to GitHub
python build.py --publish

# Build only (no version bump, no push)
python build.py

# Clean build with publish
python build.py --clean --publish

# Verbose output
python build.py --verbose --publish

# Verify existing build
python build.py --verify
```

## Content File Formats

### Text Content ({item_id}_{lang}.json)

```json
{
  "sections": [
    {
      "id": "section_name",
      "verses": [
        {
          "id": 1,
          "first": "First line of verse",
          "second": "Second line of verse"
        }
      ]
    }
  ]
}
```

### Meanings ({item_id}_meanings.json)

```json
{
  "meanings": [
    {
      "id": 1,
      "meaning": "Explanation of verse 1"
    }
  ]
}
```

## Generated Manifest

The build script generates `manifest.json` with:
- App info and configuration
- All item metadata
- SHA-256 checksums for integrity verification
- File sizes for download estimation

## Version Management

### Simple Version System

Single `version` number in `index.json`. When version changes:
1. App detects the new version
2. Clears local cache
3. Downloads all items (using checksums to skip unchanged ZIPs)

### Checksum-Based Smart Downloads

Even though cache is cleared on version change, the app uses SHA-256 checksums to:
- Skip downloading ZIPs that haven't changed
- Only download items with different checksums
- Verify integrity of downloaded files

### Quick Workflow

```bash
# 1. Edit content files in source/
# 2. Build, bump version, and push to GitHub
python build.py --publish
```

That's it! The script handles:
- Incrementing the version
- Building all ZIP bundles
- Computing checksums
- Committing and pushing to GitHub

### How Updates Work

1. App fetches `manifest.json` from server
2. Compares `version`:
   - If different → Clear cache
3. For each item, compares checksums:
   - Different checksum → Download that item
   - Same checksum → Skip (use existing file)
4. Removes items no longer in manifest
