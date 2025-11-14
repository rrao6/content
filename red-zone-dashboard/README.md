# Red Zone Analysis Dashboard

A professional web-based dashboard for viewing and analyzing movie poster red zone detection results.

## Features

- **Overview Dashboard**: Real-time statistics and trending analysis
- **Results Grid**: Browse posters with filtering by status, SOT, and search
- **Detailed View**: Individual poster analysis with red zone overlay
- **Import/Export**: Support for JSON import and export
- **Responsive Design**: Works on desktop and mobile devices
- **Professional UI**: Clean interface with Tailwind CSS

## Quick Start

### 1. Install Dependencies

```bash
cd red-zone-dashboard
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python database.py
```

### 3. Run the Dashboard

```bash
python dashboard.py
```

Visit http://localhost:5000 in your browser.

## Usage

### Import Existing Results

If you have analysis results from the main pipeline:

1. Click "Import" in navigation
2. Upload your JSON results file
3. View imported results immediately

Expected JSON format:
```json
[
  {
    "content_id": 123456,
    "program_id": 654321,
    "content_name": "Movie Title",
    "content_type": "movie",
    "sot_name": "just_added",
    "poster_img_url": "https://...",
    "analysis": {
      "red_safe_zone": {
        "contains_key_elements": true,
        "confidence": 95,
        "justification": "..."
      }
    }
  }
]
```

### Viewing Results

- **Filter by Status**: Show only pass or fail results
- **Filter by SOT**: View results from specific Sources of Truth
- **Search**: Find posters by title
- **Click posters**: View detailed analysis and justification

### Running New Analysis

If integrated with the main analysis pipeline:

1. Click "New Analysis"
2. Select Sources of Truth
3. Configure parameters (days back, sample size)
4. Start analysis and monitor progress

## Deployment

### Local Development

```bash
python dashboard.py
```

### Production (Gunicorn)

```bash
gunicorn -w 4 -b 0.0.0.0:8000 dashboard:app
```

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN python database.py

EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "dashboard:app"]
```

Build and run:
```bash
docker build -t red-zone-dashboard .
docker run -p 8000:8000 red-zone-dashboard
```

### Cloud Deployment

#### Heroku

1. Create `Procfile`:
```
web: gunicorn dashboard:app
```

2. Deploy:
```bash
heroku create red-zone-dashboard
git push heroku main
```

#### AWS Elastic Beanstalk

1. Install EB CLI
2. Initialize: `eb init -p python-3.10 red-zone-dashboard`
3. Deploy: `eb create red-zone-env`

## Configuration

Environment variables (create `.env` file):

```bash
# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=production

# Database (optional, defaults to local SQLite)
DATABASE_URL=sqlite:///red_zone_analysis.db

# Integration with main pipeline (optional)
ANALYSIS_API_URL=http://localhost:8080
ANALYSIS_API_KEY=your-api-key
```

## API Endpoints

- `GET /` - Dashboard home
- `GET /results/<run_id>` - View results for a run
- `GET /detail/<result_id>` - View single poster detail
- `POST /import` - Import JSON results
- `GET /export/<run_id>` - Export results as JSON

### JSON API

- `GET /api/runs` - List all analysis runs
- `GET /api/results?run_id=X&status=fail` - Get filtered results
- `GET /api/stats/trending` - Get trending statistics
- `POST /api/analyze` - Trigger new analysis (if integrated)

## Security Considerations

1. **Authentication**: Add Flask-Login for user management
2. **Rate Limiting**: Use Flask-Limiter for API protection
3. **HTTPS**: Always use HTTPS in production
4. **CORS**: Configure CORS appropriately for your domain

## Customization

### Branding

Edit `templates/base.html` to update:
- Logo and title
- Color scheme (update Tailwind classes)
- Footer information

### Red Zone Configuration

Modify the red zone overlay in `static/css/style.css`:
```css
.red-zone-overlay {
    width: 60%;  /* Adjust width */
    height: 10%; /* Adjust height */
}
```

## Troubleshooting

### Database Issues

Reset database:
```bash
rm red_zone_analysis.db
python database.py
```

### Import Errors

Ensure JSON format matches expected schema. Check `exports/` folder for example exports.

### Performance

For large datasets:
1. Enable pagination in results view
2. Use database indexing (already configured)
3. Implement caching with Redis

## Support

- Create issues in the repository
- Email: redzone-support@tubi.tv

## License

Copyright 2025 Tubi. All rights reserved.
