"""PDF export functionality for analysis run reports."""
import os
import json
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


class PosterAnalysisPDFGenerator:
    """Generate PDF reports for poster analysis runs."""
    
    def __init__(self, composite_images_dir: str = None):
        """
        Initialize PDF generator.
        
        Args:
            composite_images_dir: Directory containing composite poster images
        """
        if composite_images_dir is None:
            # Default to parent directory's debug_composite_images
            self.composite_dir = Path(__file__).parent.parent / "debug_composite_images"
        else:
            self.composite_dir = Path(composite_images_dir)
        
        # Set up styles
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='MovieTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='PassStatus',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#059669'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        ))
        
        self.styles.add(ParagraphStyle(
            name='FailStatus',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#dc2626'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        ))
    
    def generate_pdf(
        self,
        run_data: Dict[str, Any],
        results: List[Dict[str, Any]],
        output_path: Path
    ) -> Path:
        """
        Generate PDF report for an analysis run.
        
        Args:
            run_data: Dictionary containing run metadata
            results: List of poster analysis results
            output_path: Path where PDF should be saved
            
        Returns:
            Path to generated PDF file
        """
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=0.75*inch
        )
        
        # Build document content
        story = []
        
        # Title page
        story.extend(self._create_title_page(run_data, results))
        story.append(PageBreak())
        
        # Individual poster reports
        for idx, result in enumerate(results, 1):
            story.extend(self._create_poster_page(result, idx, len(results)))
            if idx < len(results):
                story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        
        return output_path
    
    def _create_title_page(
        self,
        run_data: Dict[str, Any],
        results: List[Dict[str, Any]]
    ) -> List:
        """Create the title/summary page."""
        story = []
        
        # Title
        title = Paragraph(
            "Poster Safe Zone Analysis Report",
            self.styles['CustomTitle']
        )
        story.append(title)
        story.append(Spacer(1, 0.3*inch))
        
        # Run information
        run_info_data = [
            ['Run ID:', str(run_data.get('id', 'N/A'))],
            ['Description:', run_data.get('description', 'N/A')],
            ['Created:', run_data.get('created_at', 'N/A')],
            ['Total Analyzed:', str(run_data.get('total_analyzed', 0))],
            ['Passed:', f"{run_data.get('pass_count', 0)} ({run_data.get('pass_count', 0) / max(run_data.get('total_analyzed', 1), 1) * 100:.1f}%)"],
            ['Failed:', f"{run_data.get('fail_count', 0)} ({run_data.get('fail_count', 0) / max(run_data.get('total_analyzed', 1), 1) * 100:.1f}%)"],
        ]
        
        run_info_table = Table(run_info_data, colWidths=[2*inch, 4.5*inch])
        run_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(run_info_table)
        story.append(Spacer(1, 0.5*inch))
        
        # Summary by SOT type
        sot_summary = {}
        for result in results:
            sot = result.get('sot_name', 'unknown')
            if sot not in sot_summary:
                sot_summary[sot] = {'total': 0, 'passed': 0, 'failed': 0}
            sot_summary[sot]['total'] += 1
            if not result.get('has_elements', True):
                sot_summary[sot]['passed'] += 1
            else:
                sot_summary[sot]['failed'] += 1
        
        if sot_summary:
            story.append(Paragraph("Results by SOT Type", self.styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            
            sot_data = [['SOT Type', 'Total', 'Passed', 'Failed', 'Fail Rate']]
            for sot, stats in sorted(sot_summary.items()):
                fail_rate = stats['failed'] / stats['total'] * 100 if stats['total'] > 0 else 0
                sot_data.append([
                    sot,
                    str(stats['total']),
                    str(stats['passed']),
                    str(stats['failed']),
                    f"{fail_rate:.1f}%"
                ])
            
            sot_table = Table(sot_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch])
            sot_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            
            story.append(sot_table)
        
        return story
    
    def _create_poster_page(
        self,
        result: Dict[str, Any],
        index: int,
        total: int
    ) -> List:
        """Create a page for individual poster analysis."""
        story = []
        
        # Page header with progress
        header = Paragraph(
            f"Poster {index} of {total}",
            self.styles['Normal']
        )
        story.append(header)
        story.append(Spacer(1, 0.1*inch))
        
        # Movie title
        movie_title = result.get('title', 'Unknown Title')
        title_para = Paragraph(
            movie_title,
            self.styles['MovieTitle']
        )
        story.append(title_para)
        
        # Pass/Fail status
        has_elements = result.get('has_elements', True)
        passed = not has_elements
        
        if passed:
            status_text = "✓ PASSED - No key elements in red safe zone"
            status_style = self.styles['PassStatus']
        else:
            status_text = "✗ FAILED - Key elements detected in red safe zone"
            status_style = self.styles['FailStatus']
        
        status_para = Paragraph(status_text, status_style)
        story.append(status_para)
        story.append(Spacer(1, 0.2*inch))
        
        # Composite image
        content_id = result.get('content_id')
        if content_id:
            image_path = self.composite_dir / f"content_{content_id}.png"
            
            if image_path.exists():
                try:
                    # Load image with PIL to compress/resize
                    from PIL import Image as PILImage
                    
                    pil_img = PILImage.open(str(image_path))
                    
                    # Resize if too large (max width 800px)
                    max_width = 800
                    if pil_img.width > max_width:
                        aspect = pil_img.height / float(pil_img.width)
                        new_height = int(max_width * aspect)
                        pil_img = pil_img.resize((max_width, new_height), PILImage.LANCZOS)
                    
                    # Save to temporary buffer as JPEG for compression
                    img_buffer = BytesIO()
                    if pil_img.mode in ('RGBA', 'LA', 'P'):
                        # Convert RGBA to RGB for JPEG
                        background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                        if pil_img.mode == 'P':
                            pil_img = pil_img.convert('RGBA')
                        background.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode in ('RGBA', 'LA') else None)
                        pil_img = background
                    
                    pil_img.save(img_buffer, format='JPEG', quality=85, optimize=True)
                    img_buffer.seek(0)
                    
                    # Create reportlab Image from buffer
                    img = Image(img_buffer)
                    
                    # Scale image to fit page width while maintaining aspect ratio
                    img_width = 4.5 * inch
                    aspect = img.imageHeight / float(img.imageWidth)
                    img.drawHeight = img_width * aspect
                    img.drawWidth = img_width
                    
                    # Center the image
                    img.hAlign = 'CENTER'
                    story.append(img)
                    story.append(Spacer(1, 0.2*inch))
                except Exception as e:
                    story.append(Paragraph(
                        f"[Image unavailable: {str(e)}]",
                        self.styles['Italic']
                    ))
                    story.append(Spacer(1, 0.2*inch))
        
        # Metadata table
        metadata_data = [
            ['Content ID:', str(content_id or 'N/A')],
            ['SOT Type:', result.get('sot_name', 'N/A')],
            ['Content Type:', result.get('content_type', 'N/A')],
            ['Confidence:', f"{result.get('confidence', 0)}%"],
        ]
        
        metadata_table = Table(metadata_data, colWidths=[1.5*inch, 5*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(metadata_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Analysis justification
        justification = result.get('justification', 'No justification provided')
        story.append(Paragraph("<b>Analysis Reason:</b>", self.styles['Heading3']))
        story.append(Spacer(1, 0.1*inch))
        
        # Clean up justification text for PDF
        justification_clean = justification.replace('\n', '<br/>')
        justification_para = Paragraph(
            justification_clean,
            self.styles['Normal']
        )
        story.append(justification_para)
        
        return story


def generate_run_pdf(
    run_id: int,
    run_data: Dict[str, Any],
    results: List[Dict[str, Any]],
    output_dir: Path,
    composite_images_dir: str = None
) -> Path:
    """
    Generate PDF report for an analysis run.
    
    Args:
        run_id: ID of the analysis run
        run_data: Run metadata dictionary
        results: List of poster analysis results
        output_dir: Directory to save PDF
        composite_images_dir: Directory containing composite images
        
    Returns:
        Path to generated PDF file
    """
    generator = PosterAnalysisPDFGenerator(composite_images_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"poster_analysis_run_{run_id}_{timestamp}.pdf"
    output_path = output_dir / filename
    
    return generator.generate_pdf(run_data, results, output_path)

