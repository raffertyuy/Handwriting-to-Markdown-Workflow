"""
PDF to image converter.
Converts the first page of a PDF to JPEG image.
"""

import logging
from io import BytesIO
from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)


def convert_pdf_to_image(pdf_bytes: bytes) -> bytes:
    """
    Convert first page of PDF to JPEG image.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        JPEG image as bytes
    """
    logger.info("Converting PDF to image...")
    
    # Convert PDF to images (only first page)
    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
    
    if not images:
        raise ValueError("Failed to extract image from PDF")
    
    # Convert PIL Image to bytes
    img = images[0]
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG', quality=95)
    img_bytes.seek(0)
    
    logger.info("PDF converted to JPEG successfully")
    return img_bytes.getvalue()

