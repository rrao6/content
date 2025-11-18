"""Flask web application for Red Zone Analysis Dashboard."""
import os
import sys
import json
import csv
from datetime import datetime
from pathlib import Path
from io import StringIO
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, Response
import requests

# Add parent directory to path to import analysis modules
sys.path.append(str(Path(__file__).parent.parent))

from database import (
    init_database, AnalysisRun, PosterResult, 
    import_json_results, get_db_connection
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['EXPORT_FOLDER'] = Path('exports')

# Ensure directories exist
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
app.config['EXPORT_FOLDER'].mkdir(exist_ok=True)


@app.route('/')
def dashboard():
    """Main dashboard view with statistics."""
    # Get latest run
    latest_run = AnalysisRun.get_latest()
    
    # Get overall stats
    stats = PosterResult.get_stats()
    
    # Get trending data
    trending_data = PosterResult.get_trending_data(days=30)
    
    # Get recent runs
    recent_runs = AnalysisRun.get_all(limit=10)
    
    return render_template('dashboard.html',
                         latest_run=latest_run,
                         stats=stats,
                         trending_data=json.dumps(trending_data),
                         recent_runs=recent_runs)


@app.route('/results')
@app.route('/results/<int:run_id>')
def results(run_id=None):
    """Results grid view."""
    # If no run_id specified, use latest
    if run_id is None:
        latest_run = AnalysisRun.get_latest()
        if latest_run:
            return redirect(url_for('results', run_id=latest_run['id']))
        else:
            return render_template('no_results.html')
    
    # Get run details
    run = AnalysisRun.get_by_id(run_id)
    if not run:
        return "Run not found", 404
    
    # Parse parameters if they're JSON
    if run['parameters']:
        try:
            run['parameters'] = json.loads(run['parameters'])
        except:
            pass
    
    # Get filters from query params
    filters = {}
    if request.args.get('status') == 'pass':
        filters['has_elements'] = 0
    elif request.args.get('status') == 'fail':
        filters['has_elements'] = 1
    
    if request.args.get('sot'):
        filters['sot_name'] = request.args.get('sot')
    
    if request.args.get('search'):
        filters['search'] = request.args.get('search')
    
    # Get results with filters
    results = PosterResult.get_by_run(run_id, filters)
    
    # Get unique SOT names for filter dropdown
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT sot_name 
            FROM poster_results 
            WHERE run_id = ? 
            ORDER BY sot_name
        """, (run_id,))
        sot_names = [row[0] for row in cursor.fetchall()]
    
    return render_template('results.html',
                         run=run,
                         results=results,
                         sot_names=sot_names,
                         filters=filters)


@app.route('/detail/<int:result_id>')
def detail(result_id):
    """Detailed view of a single poster result."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.*, ar.created_at as run_date
            FROM poster_results pr
            JOIN analysis_runs ar ON pr.run_id = ar.id
            WHERE pr.id = ?
        """, (result_id,))
        result = cursor.fetchone()
    
    if not result:
        return "Result not found", 404
    
    result = dict(result)
    
    # Parse analysis JSON
    if result['analysis_json']:
        result['analysis'] = json.loads(result['analysis_json'])
    
    return render_template('detail.html', result=result)


@app.route('/api/runs')
def api_runs():
    """API endpoint to list analysis runs."""
    runs = AnalysisRun.get_all(limit=100)
    return jsonify(runs)


@app.route('/api/results')
def api_results():
    """API endpoint for results with filtering."""
    run_id = request.args.get('run_id', type=int)
    if not run_id:
        return jsonify({"error": "run_id required"}), 400
    
    filters = {}
    if request.args.get('status') == 'pass':
        filters['has_elements'] = 0
    elif request.args.get('status') == 'fail':
        filters['has_elements'] = 1
    
    if request.args.get('sot'):
        filters['sot_name'] = request.args.get('sot')
    
    if request.args.get('search'):
        filters['search'] = request.args.get('search')
    
    results = PosterResult.get_by_run(run_id, filters)
    return jsonify(results)


@app.route('/api/stats/trending')
def api_trending():
    """API endpoint for trending statistics."""
    days = request.args.get('days', 30, type=int)
    data = PosterResult.get_trending_data(days)
    return jsonify(data)


@app.route('/api/result/<int:result_id>')
def api_get_result(result_id):
    """API endpoint to get a single result."""
    result = PosterResult.get_by_id(result_id)
    if not result:
        return jsonify({"error": "Result not found"}), 404
    return jsonify(result)


@app.route('/api/result/<int:result_id>/qa', methods=['PUT'])
def api_update_qa(result_id):
    """API endpoint to update QA status of a result."""
    data = request.json
    
    if 'has_elements' not in data or 'justification' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    has_elements = bool(data['has_elements'])
    justification = data['justification']
    
    success = PosterResult.update_qa_status(result_id, has_elements, justification)
    
    if success:
        return jsonify({
            "success": True,
            "message": "QA status updated successfully"
        })
    else:
        return jsonify({"error": "Failed to update result"}), 500


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Trigger new analysis."""
    from analyzer import analyzer, is_analysis_available
    
    # Always try real analysis first
    if is_analysis_available():
        data = request.json
        
        result = analyzer.run_analysis(
            sot_types=data.get('sot_types', ['just_added']),
            days_back=data.get('days_back', 7),
            limit=data.get('limit'),
            description=data.get('description', ''),
            use_cache=data.get('use_cache', True)
        )
        return jsonify(result)
    else:
        # If analysis isn't available, create a demo run with test data
        import random
        from pathlib import Path
        
        # Generate demo data
        num_posters = request.json.get('limit', 50)
        sot_types = request.json.get('sot_types', ['just_added'])
        description = request.json.get('description', 'Demo analysis run')
        
        # Create fake results
        results = []
        for i in range(num_posters):
            has_elements = random.random() > 0.2  # 80% fail rate
            results.append({
                "content_id": 300000 + i,
                "program_id": 400000 + i, 
                "content_name": f"Demo Content {i:04d}",
                "content_type": "movie" if i % 3 != 0 else "series",
                "sot_name": random.choice(sot_types),
                "poster_img_url": f"https://via.placeholder.com/270x480/{'ff6b6b' if has_elements else '51cf66'}/ffffff?text=Demo+{i:04d}",
                "analysis": {
                    "red_safe_zone": {
                        "contains_key_elements": has_elements,
                        "confidence": random.randint(85, 99),
                        "justification": "Demo analysis result"
                    }
                }
            })
        
        # Save and import
        demo_file = Path(app.config['UPLOAD_FOLDER']) / f"demo_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(demo_file, 'w') as f:
            json.dump(results, f)
        
        try:
            run_id = import_json_results(demo_file, description)
            return jsonify({
                "status": "success",
                "run_id": run_id,
                "message": f"Demo analysis completed with {num_posters} posters",
                "is_demo": True
            })
        finally:
            if demo_file.exists():
                demo_file.unlink()


@app.route('/analyze')
def analyze():
    """Analysis configuration page."""
    return render_template('analyze.html')


@app.route('/import', methods=['GET', 'POST'])
def import_results():
    """Import results from JSON file."""
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file and file.filename.endswith('.json'):
            # Save uploaded file
            filename = Path(app.config['UPLOAD_FOLDER']) / file.filename
            file.save(filename)
            
            # Import to database
            description = request.form.get('description', '')
            try:
                run_id = import_json_results(filename, description)
                return redirect(url_for('results', run_id=run_id))
            except Exception as e:
                return f"Import failed: {str(e)}", 500
    
    return render_template('import.html')


@app.route('/qa-guide')
def qa_guide():
    """QA guide page."""
    return render_template('qa_guide.html')


@app.route('/export/<int:run_id>')
def export_run(run_id):
    """Export results as JSON."""
    run = AnalysisRun.get_by_id(run_id)
    if not run:
        return "Run not found", 404
    
    results = PosterResult.get_by_run(run_id)
    
    # Add QA information to each result
    for result in results:
        result['sot_label'] = 'fail' if result.get('has_elements') else 'pass'
        if result.get('qa_reviewed'):
            result['qa_info'] = {
                'reviewed': True,
                'modified_at': result.get('qa_modified_at'),
                'original_label': 'fail' if result.get('original_has_elements') else 'pass' if result.get('original_has_elements') is not None else None,
                'original_justification': result.get('original_justification')
            }
        else:
            result['qa_info'] = {'reviewed': False}
    
    # Format for export
    export_data = {
        "run": run,
        "results": results,
        "exported_at": datetime.now().isoformat(),
        "qa_summary": {
            "total_reviewed": sum(1 for r in results if r.get('qa_reviewed')),
            "total_results": len(results)
        }
    }
    
    # Save to file
    filename = f"red_zone_analysis_run_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = app.config['EXPORT_FOLDER'] / filename
    
    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route('/export/pdf/<int:run_id>')
def export_run_pdf(run_id):
    """Export results as PDF with composite images."""
    from pdf_export import generate_run_pdf
    
    run = AnalysisRun.get_by_id(run_id)
    if not run:
        return "Run not found", 404
    
    results = PosterResult.get_by_run(run_id)
    
    # Get composite images directory
    composite_images_dir = Path(__file__).parent.parent / "debug_composite_images"
    
    try:
        # Generate PDF
        pdf_path = generate_run_pdf(
            run_id=run_id,
            run_data=run,
            results=results,
            output_dir=app.config['EXPORT_FOLDER'],
            composite_images_dir=str(composite_images_dir)
        )
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_path.name,
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"PDF generation failed: {str(e)}", 500


@app.route('/export/csv/<int:run_id>')
def export_run_csv(run_id):
    """Export results as CSV."""
    run = AnalysisRun.get_by_id(run_id)
    if not run:
        return "Run not found", 404
    
    results = PosterResult.get_by_run(run_id)
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'content_id',
        'program_id',
        'title',
        'content_type',
        'sot_name',
        'poster_url',
        'sot_label',
        'confidence',
        'explanation',
        'analysis_date',
        'run_id',
        'qa_reviewed',
        'qa_modified_at',
        'original_label',
        'original_explanation'
    ])
    
    # Write data rows
    for result in results:
        # Determine pass/fail label
        has_elements = result.get('has_elements', True)
        sot_label = 'fail' if has_elements else 'pass'
        
        # Original label if QA reviewed
        original_label = ''
        if result.get('qa_reviewed') and result.get('original_has_elements') is not None:
            original_label = 'fail' if result.get('original_has_elements') else 'pass'
        
        writer.writerow([
            result.get('content_id', ''),
            result.get('program_id', ''),
            result.get('title', ''),
            result.get('content_type', ''),
            result.get('sot_name', ''),
            result.get('poster_url', ''),
            sot_label,
            result.get('confidence', ''),
            result.get('justification', ''),
            result.get('created_at', ''),
            run_id,
            'Yes' if result.get('qa_reviewed') else 'No',
            result.get('qa_modified_at', ''),
            original_label,
            result.get('original_justification', '')
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"red_zone_analysis_run_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )


@app.route('/debug_composite_images/<path:filename>')
def serve_composite_image(filename):
    """Serve composite debug images."""
    import os
    composite_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'debug_composite_images')
    
    # Security: prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        return "Invalid filename", 400
    
    filepath = os.path.join(composite_dir, filename)
    
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    else:
        # Return placeholder if composite doesn't exist
        return placeholder_image()


@app.route('/proxy/image')
def proxy_image():
    """Proxy images to handle HTTP/HTTPS and CORS issues."""
    url = request.args.get('url')
    
    # Security: Basic validation to prevent SSRF
    if not url:
        return placeholder_image()
    
    # Only allow specific domains
    allowed_domains = ['img.adrise.tv', 'adrise.tv', 'image.tmdb.org', 'themoviedb.org']
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not any(domain in parsed.netloc for domain in allowed_domains):
        return placeholder_image()
    
    try:
        # Download image server-side with timeout
        response = requests.get(url, timeout=10, stream=True, 
                              headers={'User-Agent': 'Mozilla/5.0 (compatible; RedZoneDashboard/1.0)'})
        response.raise_for_status()
        
        # Get content type
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        # Check if it's actually an image
        # Note: img.adrise.tv returns 'application/octet-stream' for images,
        # so we need to infer the type from the URL extension
        if not content_type.startswith('image/'):
            # Infer content type from URL extension
            if url.lower().endswith('.jpg') or url.lower().endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif url.lower().endswith('.png'):
                content_type = 'image/png'
            elif url.lower().endswith('.gif'):
                content_type = 'image/gif'
            elif url.lower().endswith('.webp'):
                content_type = 'image/webp'
            elif 'img.adrise.tv' in parsed.netloc:
                # For adrise.tv, assume JPEG if no extension match
                content_type = 'image/jpeg'
            else:
                # For other domains, reject non-image content types
                return placeholder_image()
        
        # Stream back to client
        return Response(
            response.iter_content(chunk_size=8192),
            mimetype=content_type,
            headers={
                'Cache-Control': 'public, max-age=86400',  # Cache for 24 hours
                'X-Original-URL': url,
                'Access-Control-Allow-Origin': '*'  # Allow CORS
            }
        )
    except requests.exceptions.RequestException as e:
        app.logger.warning(f"Failed to proxy image from {url}: {e}")
        return placeholder_image()
    except Exception as e:
        app.logger.error(f"Unexpected error proxying image from {url}: {e}")
        return placeholder_image()


def placeholder_image():
    """Return a placeholder image when the original fails to load."""
    # Create a movie poster-style SVG placeholder
    svg = '''<svg width="270" height="480" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="bg-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#374151;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#111827;stop-opacity:1" />
            </linearGradient>
            <filter id="shadow">
                <feGaussianBlur in="SourceAlpha" stdDeviation="3"/>
                <feOffset dx="2" dy="2" result="offsetblur"/>
                <feFlood flood-color="#000000" flood-opacity="0.5"/>
                <feComposite in2="offsetblur" operator="in"/>
                <feMerge>
                    <feMergeNode/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        
        <!-- Background -->
        <rect width="100%" height="100%" fill="url(#bg-gradient)"/>
        
        <!-- Film strip decoration -->
        <rect x="0" y="0" width="15" height="100%" fill="#1f2937" opacity="0.5"/>
        <rect x="255" y="0" width="15" height="100%" fill="#1f2937" opacity="0.5"/>
        
        <!-- Film perforations -->
        <g opacity="0.3">
            <rect x="2" y="10" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="2" y="35" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="2" y="60" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="2" y="85" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="2" y="110" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="258" y="10" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="258" y="35" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="258" y="60" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="258" y="85" width="10" height="15" rx="2" fill="#374151"/>
            <rect x="258" y="110" width="10" height="15" rx="2" fill="#374151"/>
        </g>
        
        <!-- Film icon -->
        <g transform="translate(135, 180)" opacity="0.4">
            <path d="M0 0h24v24H0z" fill="none"/>
            <path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" 
                  fill="#6b7280" transform="scale(3)"/>
        </g>
        
        <!-- Text -->
        <text x="50%" y="65%" font-family="Arial, sans-serif" font-size="18" fill="#9ca3af" 
              text-anchor="middle" dominant-baseline="middle" filter="url(#shadow)">
            POSTER
        </text>
        <text x="50%" y="72%" font-family="Arial, sans-serif" font-size="14" fill="#6b7280" 
              text-anchor="middle" dominant-baseline="middle">
            NOT AVAILABLE
        </text>
        
        <!-- Border -->
        <rect x="1" y="1" width="268" height="478" fill="none" stroke="#374151" stroke-width="2" rx="4"/>
    </svg>'''
    
    return Response(svg, mimetype='image/svg+xml', headers={
        'Cache-Control': 'public, max-age=3600',
        'Content-Type': 'image/svg+xml'
    })


@app.template_filter('format_datetime')
def format_datetime(value):
    """Format datetime for display."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    return value.strftime('%b %d, %Y %I:%M %p')


@app.template_filter('format_percentage')
def format_percentage(value):
    """Format percentage for display."""
    return f"{value:.1f}%"


@app.template_filter('from_json')
def from_json(value):
    """Parse JSON string to dict."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return {}
    return value or {}


@app.errorhandler(404)
def not_found(error):
    """404 error handler."""
    return render_template('404.html'), 404


if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Run Flask app
    app.run(debug=True, port=5000)
