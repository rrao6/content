# Repository Organization

This document describes the organization of documentation and markdown files in this repository.

## Directory Structure

```
/
├── README.md                    # Main project README
├── readME                       # Original README (legacy)
│
├── docs/                        # 📚 Documentation & Guides
│   ├── README.md
│   ├── COMPOSITE_IMAGES_GUIDE.md
│   └── PRODUCTION_GUIDE.md
│
├── changelog/                   # 📝 Historical Records & Updates
│   ├── README.md
│   ├── ANALYSIS_RUN_100_SOT_POSTERS.md
│   ├── ANALYSIS_RUN_SUMMARY.md
│   ├── FINAL_SYSTEM_SUMMARY.md
│   ├── PDF_EXPORT_FEATURE.md
│   ├── PROGRESS_TRACKING_IMPROVEMENTS.md
│   └── PROGRESS_UPDATE_COMPLETE.md
│
├── red-zone-dashboard/
│   ├── README.md                # Dashboard README
│   │
│   ├── docs/                    # 📚 Dashboard Documentation
│   │   ├── README.md
│   │   ├── DEPLOYMENT_GUIDE.md
│   │   ├── QUICK_START.md
│   │   └── RESTART_INSTRUCTIONS.md
│   │
│   └── changelog/               # 📝 Dashboard Updates
│       ├── README.md
│       ├── EVERYTHING_IS_WORKING.md
│       ├── FULL_RELIABILITY_SUMMARY.md
│       ├── IMAGE_PROXY_FIX.md
│       ├── IMAGE_RENDERING_FIXED.md
│       ├── PRODUCTION_READY_SUMMARY.md
│       └── QA_SETUP_SUMMARY.md
```

## Organization Principles

### Documentation (`docs/`)
Technical guides, setup instructions, and reference materials:
- How-to guides
- Configuration guides
- Production setup documentation

### Changelog (`changelog/`)
Historical records of features, improvements, and analysis runs:
- Feature implementation summaries
- Progress updates
- Analysis run results
- System improvements

### Root Level
Only essential files remain at the root:
- `README.md` - Main project documentation
- Configuration files (`.gitignore`, `.env`, etc.)
- Source code files

## Quick Reference

### For Users
- **Getting Started**: See main `README.md`
- **Dashboard Setup**: See `red-zone-dashboard/docs/QUICK_START.md`
- **Production Deployment**: See `docs/PRODUCTION_GUIDE.md`

### For Developers
- **System Overview**: See `changelog/FINAL_SYSTEM_SUMMARY.md`
- **Recent Features**: Browse `changelog/` directory
- **Dashboard Features**: Browse `red-zone-dashboard/changelog/` directory

## Gitignore Updates

The following directories are now ignored:
- `exports/` - Generated export files
- `red-zone-dashboard/exports/` - Dashboard export files
- `debug_composite_images/` - Composite image cache
- `*.json` files (except `package.json` and `package-lock.json`)

## Navigation Tips

All directory READMEs contain:
- Overview of contained files
- Cross-references to related documentation
- Quick navigation links

Example workflow:
1. Start with root `README.md` for project overview
2. Check `docs/` for guides and setup
3. Review `changelog/` for recent updates and features
4. Explore `red-zone-dashboard/` subdirectories for dashboard-specific content

