"""Create demo movie posters for testing."""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random

def create_movie_poster(title, content_id, output_dir="static/posters", fail=True):
    """Create a movie poster-like image with title."""
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Create image
    width, height = 270, 480
    
    # Colors
    if fail:
        # Dark colors for movies that fail (have elements in red zone)
        bg_colors = [(45, 52, 54), (44, 62, 80), (52, 73, 94)]
        text_color = (255, 255, 255)
        accent_color = (231, 76, 60)  # Red
    else:
        # Lighter colors for movies that pass
        bg_colors = [(46, 204, 113), (39, 174, 96), (32, 140, 77)]
        text_color = (255, 255, 255)
        accent_color = (52, 231, 130)  # Green
    
    bg_color = random.choice(bg_colors)
    
    # Create image
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fallback to default if not available
    try:
        # Try different font sizes
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Add some visual elements to make it look like a poster
    # Add gradient effect
    for i in range(height // 2):
        alpha = i / (height // 2)
        overlay_color = tuple(int(c * (1 - alpha * 0.3)) for c in bg_color)
        draw.rectangle([(0, i), (width, i + 1)], fill=overlay_color)
    
    # Add title at the top (this might be in the red zone for fail cases)
    title_y = 30 if fail else 80  # Position title in red zone for fail cases
    
    # Wrap title text
    words = title.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        test_line = ' '.join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] > width - 40:
            if len(current_line) > 1:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(test_line)
                current_line = []
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # Draw title
    y_offset = title_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_offset), line, fill=text_color, font=title_font)
        y_offset += 35
    
    # Add some decorative elements
    # Add a subtle frame
    draw.rectangle([(10, 10), (width-10, height-10)], outline=accent_color, width=2)
    
    # Add bottom text
    draw.text((width//2, height-50), "STREAMING NOW", fill=text_color, font=small_font, anchor="mm")
    
    # Add some visual interest - random shapes or patterns
    if fail:
        # Add actor silhouette in top area (to trigger red zone)
        draw.ellipse([(20, 40), (80, 100)], fill=(255, 255, 255, 50))
    
    # Save image
    filename = f"poster_{content_id}.png"
    filepath = os.path.join(output_dir, filename)
    img.save(filepath, quality=95)
    
    return f"/static/posters/{filename}"


def generate_all_demo_posters():
    """Generate demo posters for the dashboard."""
    from fix_dashboard import MOVIE_TITLES, SERIES_TITLES
    
    print("🎬 Generating demo movie posters...")
    
    all_titles = MOVIE_TITLES + SERIES_TITLES
    poster_urls = {}
    
    for i, title in enumerate(all_titles[:50]):  # Generate first 50
        content_id = 100001 + i
        # 80% fail rate
        fail = i % 5 != 0
        url = create_movie_poster(title, content_id, fail=fail)
        poster_urls[content_id] = url
        print(f"  Created poster for: {title}")
    
    print(f"✅ Generated {len(poster_urls)} demo posters!")
    return poster_urls


if __name__ == "__main__":
    # Check if Pillow is installed
    try:
        generate_all_demo_posters()
    except ImportError:
        print("❌ Pillow not installed. Using online placeholders instead.")
        print("   To generate custom posters, run: pip install Pillow")
