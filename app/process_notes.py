#!/usr/bin/env python3
"""
Main script to process handwritten notes from OneDrive.
This script replaces the Azure Logic App functionality.
"""

import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Add current directory to path to import local modules
sys.path.insert(0, str(Path(__file__).parent))

from onedrive_client import OneDriveClient
from note_processor import NoteProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to process handwritten notes."""
    
    # Get environment variables
    client_id = os.environ.get("ONEDRIVE_CLIENT_ID")
    client_secret = os.environ.get("ONEDRIVE_CLIENT_SECRET")
    refresh_token = os.environ.get("ONEDRIVE_REFRESH_TOKEN")
    # GH_TOKEN uses a Personal Access Token with 'copilot' scope
    github_token = os.environ.get("GH_TOKEN")
    github_model = os.environ.get("GH_MODEL") or "openai/gpt-4.1"
    github_models_url = os.environ.get("GH_MODELS_URL") or "https://models.github.ai/inference"
    
    # Get folder paths, treating empty strings as unset (use defaults)
    source_folder = os.environ.get("ONEDRIVE_SOURCE_FOLDER") or "Handwritten Notes"
    dest_folder = os.environ.get("ONEDRIVE_DEST_FOLDER") or "second-brain/second-brain/_scans"
    processed_folder = os.environ.get("ONEDRIVE_PROCESSED_FOLDER") or "Handwritten Notes/processed"
    
    # Validate required environment variables
    if not all([client_id, client_secret, refresh_token]):
        logger.error("Missing required OneDrive environment variables. Please check your GitHub secrets.")
        sys.exit(1)
    
    # Validate GitHub token
    if not github_token:
        logger.error("GITHUB_TOKEN is required for GitHub Copilot Models.")
        logger.error("GITHUB_TOKEN is automatically available in GitHub Actions.")
        logger.error("Ensure your account has access to GitHub Copilot Models.")
        sys.exit(1)
    
    try:
        # Initialize OneDrive client
        logger.info("Initializing OneDrive client...")
        onedrive = OneDriveClient(client_id, client_secret, refresh_token)
        
        # Initialize note processor
        logger.info("Initializing note processor with GitHub Copilot Models...")
        processor = NoteProcessor(
            github_token=github_token,
            model=github_model,
            base_url=github_models_url
        )
        
        # Get list of files in source folder
        logger.info(f"Checking for new files in '{source_folder}'...")
        files = onedrive.list_files(source_folder)
        
        if not files:
            logger.info("No files found to process.")
            return
        
        # Filter out files in processed subfolder and skip folders
        files = [
            f for f in files 
            if 'folder' not in f and not f.get('name', '').startswith('processed/')
        ]
        
        # Supported image extensions
        supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.pdf'}
        
        # Process each file
        processed_count = 0
        for file_info in files:
            file_name = file_info['name']
            file_path = f"{source_folder}/{file_name}"
            
            # Get file extension
            file_ext = Path(file_name).suffix.lower()
            
            # Skip if not a supported file type
            if file_ext not in supported_extensions:
                logger.info(f"Skipping unsupported file type: {file_name}")
                continue
            
            # Skip if already processed (check if exists in processed folder)
            processed_path = f"{processed_folder}/{file_name}"
            try:
                if onedrive.file_exists(processed_path):
                    logger.info(f"File already processed: {file_name}")
                    continue
            except Exception as e:
                logger.warning(f"Could not check if file exists in processed folder: {e}")
                # Continue processing anyway
            
            try:
                logger.info(f"Processing file: {file_name}")
                
                # Download file
                file_content = onedrive.download_file(file_path)
                
                # Convert PDF to image if needed
                if file_ext == '.pdf':
                    logger.info("Converting PDF to image...")
                    from pdf_converter import convert_pdf_to_image
                    image_bytes = convert_pdf_to_image(file_content)
                    file_ext = '.jpg'  # Update extension for output
                else:
                    image_bytes = file_content
                
                # Process the image
                logger.info("Extracting text from image...")
                result = processor.process_image(image_bytes)
                
                # Create markdown content
                markdown_content = create_markdown_content(
                    result['noteType'],
                    result['extractedTitle'],
                    result['extractedText'],
                    file_ext
                )
                
                # Save markdown file
                markdown_filename = f"{result['extractedTitle']}.md"
                markdown_path = f"{dest_folder}/{markdown_filename}"
                logger.info(f"Saving markdown file: {markdown_path}")
                onedrive.upload_file(markdown_path, markdown_content.encode('utf-8'), 'text/markdown')
                
                # Copy image to destination folder
                image_filename = f"{result['extractedTitle']}{file_ext}"
                image_path = f"{dest_folder}/{image_filename}"
                logger.info(f"Copying image to: {image_path}")
                onedrive.upload_file(image_path, image_bytes, f'image/{file_ext[1:]}')
                
                # Move original file to processed folder
                logger.info(f"Moving file to processed folder: {processed_path}")
                onedrive.move_file(file_path, processed_path)
                
                processed_count += 1
                logger.info(f"Successfully processed: {file_name}")
                
            except Exception as e:
                logger.error(f"Error processing file {file_name}: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"Processing complete. Processed {processed_count} file(s).")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


def create_markdown_content(note_type, title, text, image_ext):
    """Create markdown content with frontmatter."""
    now = datetime.now()
    created_date = now.strftime('%Y-%m-%d %H:%M')
    
    # Use Obsidian image link format
    image_filename = f"{title}{image_ext}"
    
    content = f"""---
note-type: {note_type}
created-date: {created_date}
last-updated: {created_date}
---

![[{image_filename}]]

{text}
"""
    return content


if __name__ == "__main__":
    main()

