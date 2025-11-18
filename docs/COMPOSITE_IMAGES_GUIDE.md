# Composite Image Verification Guide

This guide explains how to save and review composite images with red zone overlays to verify the safe zone positioning.

## Overview

The system can now save composite images showing:
- The original movie poster
- A **red rectangle overlay** marking the safe zone (top-left 60% width × 10% height)

These images are exactly what gets sent to GPT for analysis, allowing you to visually verify the red zone positioning.

## Quick Start

### Option 1: Use the Test Script (Recommended)

Run the included test script to analyze 5 posters and save composite images:

```bash
python test_composite_images.py
```

This will:
1. Analyze 5 movie posters
2. Save composite images to `./debug_composite_images/`
3. Show you the analysis results
4. Each image will be named `content_{CONTENT_ID}.png`

### Option 2: Use CLI Flags

Add the `--save-composite-images` flag to any analysis command:

```bash
# Analyze 10 posters and save composite images
python main.py analyze-posters \
  --limit 10 \
  --save-composite-images \
  --composite-image-dir ./my_debug_images

# Or use the default directory (./debug_composite_images)
python main.py analyze-posters --limit 5 --save-composite-images
```

### Option 3: Programmatic Usage

```python
from config import get_config
from service import ContentService
from analysis import SafeZoneAnalyzer, PosterAnalysisPipeline

# Setup
config = get_config()
analyzer = SafeZoneAnalyzer(
    provider="openai",
    model=config.openai_model,
    api_key=config.openai_api_key,
)
pipeline = PosterAnalysisPipeline(ContentService(), analyzer)

# Run with composite image saving
results = pipeline.run(
    limit=10,
    save_composite_images=True,
    composite_image_dir="./debug_composite_images",
)
```

## What to Look For

When reviewing the composite images:

### ✅ Correct Red Zone Position
- Red rectangle should be in the **top-left corner**
- Width: **60% of poster width**
- Height: **10% of poster height**
- Border: **3px thick red line** (matching dashboard overlay)

### 🔍 Verification Checklist
1. **Position**: Top-left corner (0,0) starting point
2. **Size**: Rectangle covers ~60% horizontal, ~10% vertical
3. **Clarity**: Red border is clearly visible
4. **Accuracy**: Matches what you see in the dashboard

## File Naming

Composite images are named by content ID:
```
debug_composite_images/
  ├── content_12345.png
  ├── content_67890.png
  └── content_11111.png
```

## Integration with Dashboard

The red zone overlay in the composite images uses:
- **Same dimensions** as dashboard CSS (60% × 10%)
- **Same border thickness** (3px)
- **Same color** (red)

This ensures the images sent to GPT match what users see in the dashboard.

## Advanced Usage

### Custom Output Directory

```bash
python main.py analyze-posters \
  --limit 20 \
  --save-composite-images \
  --composite-image-dir ./verification_images
```

### Batch Processing with Composite Images

For SOT pipeline analysis:

```python
from sot_pipeline import SOTAnalysisPipeline
from service import EligibleTitlesService, ContentService
from analysis import SafeZoneAnalyzer
from config import get_config

config = get_config()
analyzer = SafeZoneAnalyzer(
    provider="openai",
    model=config.openai_model,
    api_key=config.openai_api_key,
)

pipeline = SOTAnalysisPipeline(
    eligible_service=EligibleTitlesService(),
    content_service=ContentService(),
    analyzer=analyzer,
)

results = pipeline.run(
    days_back=7,
    sot_types=["imdb", "rotten_tomatoes"],
    limit=50,
    save_composite_images=True,
    composite_image_dir="./sot_verification",
)
```

## Cleanup

The `debug_composite_images/` directory is in `.gitignore` and won't be committed.

To clean up:
```bash
rm -rf debug_composite_images/
```

## Troubleshooting

### No images saved?
- Ensure `--save-composite-images` flag is set
- Check that analysis is actually running (not just using cache)
- Verify the output directory is writable

### Images don't match dashboard?
- The red zone overlay uses the same 3px border thickness
- Check that PIL/Pillow is properly installed
- Verify image dimensions are being calculated correctly

### Red zone looks wrong?
1. Check the poster's aspect ratio
2. Measure the red rectangle dimensions
3. Verify: `zone_width = poster_width * 0.60`
4. Verify: `zone_height = poster_height * 0.10`

## Technical Details

### Red Zone Calculation
```python
zone_width = int(poster_width * 0.60)   # 60% of width
zone_height = int(poster_height * 0.10)  # 10% of height
```

### Overlay Implementation
- Uses PIL (Pillow) `ImageDraw.rectangle()`
- 3px border created by drawing 3 overlapping rectangles
- Saved as PNG with 95% quality
- Base64-encoded for OpenAI API

### Performance Impact
- **Minimal** - images are already being downloaded and processed
- Only adds ~10-50ms per image for saving to disk
- No impact on API calls or analysis accuracy

## Next Steps

After verifying the red zone positioning:
1. Review sample composite images
2. Compare with dashboard overlay
3. Confirm with team that positioning is correct
4. Run production analysis without `--save-composite-images` flag

