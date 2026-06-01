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
# Clean build
python build.py --clean

# Normal build
python build.py

# Verbose output
python build.py --verbose

# Verify existing build
python build.py --verify
```

### 4. Deploy to GitHub

Upload the contents of `build/` directory to your GitHub data repository:
- `manifest.json` - Main manifest file
- `texts/*.zip` - Content bundles

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

To release a content update:
1. Update content files in `source/`
2. Increment `contentVersion` in `index.json`
3. Run `python build.py --clean`
4. Deploy `build/` to GitHub

The app will detect the new version and download updated content.
