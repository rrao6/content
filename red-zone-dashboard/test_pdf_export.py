#!/usr/bin/env python3
"""Test script for PDF export functionality."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import AnalysisRun, PosterResult
from pdf_export import generate_run_pdf

def test_pdf_export():
    """Test PDF generation for Run 17 (Shiny SOT Analysis)."""
    
    run_id = 17
    
    print("🧪 Testing PDF Export")
    print("=" * 80)
    
    # Get run data
    print(f"\n1️⃣ Fetching run data for Run ID {run_id}...")
    run = AnalysisRun.get_by_id(run_id)
    
    if not run:
        print(f"❌ Run {run_id} not found!")
        return False
    
    print(f"✅ Run found: {run['description']}")
    print(f"   Total: {run['total_analyzed']}, Passed: {run['pass_count']}, Failed: {run['fail_count']}")
    
    # Get results
    print(f"\n2️⃣ Fetching poster results...")
    results = PosterResult.get_by_run(run_id)
    print(f"✅ Found {len(results)} results")
    
    # Generate PDF
    print(f"\n3️⃣ Generating PDF...")
    output_dir = Path(__file__).parent / "exports"
    output_dir.mkdir(exist_ok=True)
    
    composite_images_dir = Path(__file__).parent.parent / "debug_composite_images"
    
    try:
        pdf_path = generate_run_pdf(
            run_id=run_id,
            run_data=run,
            results=results,
            output_dir=output_dir,
            composite_images_dir=str(composite_images_dir)
        )
        
        print(f"✅ PDF generated successfully!")
        print(f"\n📄 PDF Location: {pdf_path}")
        print(f"📦 File size: {pdf_path.stat().st_size / 1024:.1f} KB")
        print(f"\n🎉 Test passed!")
        return True
        
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pdf_export()
    sys.exit(0 if success else 1)

