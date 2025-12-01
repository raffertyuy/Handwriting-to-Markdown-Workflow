"""
Note processor that uses GitHub Copilot Models API to extract text from images.
Replaces Azure Function functionality.
"""

import logging
import base64
import os
from pathlib import Path

from openai import OpenAI
from image_processor import execute_image_completion, execute_text_completion, read_file
from post_processor import remove_markdown_code_blocks, add_datestamp

logger = logging.getLogger(__name__)


class NoteProcessor:
    """Processor for extracting text from handwritten notes using GitHub Copilot Models."""
    
    def __init__(self, github_token: str, model: str = "openai/gpt-4.1", base_url: str = None):
        """
        Initialize note processor.
        
        Args:
            github_token: GitHub token for authentication (GITHUB_TOKEN)
            model: Model name (default: openai/gpt-4.1)
            base_url: Custom base URL for GitHub Models API (if different from default)
        """
        if not github_token:
            raise ValueError("github_token is required for GitHub Copilot Models")
        
        # GitHub Models API endpoint
        # Official endpoint: https://models.github.ai/inference
        # Reference: https://github.com/marketplace/models/azure-openai/gpt-4-1/playground/code
        github_models_url = base_url or os.environ.get(
            "GH_MODELS_URL", 
            "https://models.github.ai/inference"
        )
        logger.info(f"Using GitHub Copilot Models API with endpoint: {github_models_url}")
        logger.info(f"Using model: {model}")
        
        # Use GitHub token for authentication
        self.client = OpenAI(
            api_key=github_token,
            base_url=github_models_url
        )
        self.model = model
        self.vision_temperature = 0
        self.text_temperature = 0.3
        
        # Load prompts
        prompts_dir = Path(__file__).parent / "prompts"
        self.prompts = {
            'detectNoteType': read_file(str(prompts_dir / "detectNoteType.txt")),
            'ocrImage': read_file(str(prompts_dir / "ocrImage.txt")),
            'ocrPaper': read_file(str(prompts_dir / "ocrPaper.txt")),
            'ocrWhiteboard': read_file(str(prompts_dir / "ocrWhiteboard.txt")),
            'proofread': read_file(str(prompts_dir / "proofread.txt")),
            'sectionHeader': read_file(str(prompts_dir / "sectionHeader.txt")),
            'extractMainTitle': read_file(str(prompts_dir / "extractMainTitle.txt"))
        }
    
    def process_image(self, image_bytes: bytes) -> dict:
        """
        Process image and extract text.
        
        Args:
            image_bytes: Image file content as bytes
            
        Returns:
            Dictionary with noteType, extractedTitle, and extractedText
        """
        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Identify image note type
        logger.info("Detecting note type...")
        note_type = execute_image_completion(
            self.client,
            image_base64,
            self.prompts['detectNoteType'],
            self.model,
            self.vision_temperature
        )
        
        # Extract text from the image
        logger.info(f"Extracting text (note type: {note_type})...")
        ocr_prompt = self.prompts['ocrImage']
        if note_type == "PAPER":
            ocr_prompt = self.prompts['ocrPaper']
        elif note_type == "WHITEBOARD":
            ocr_prompt = self.prompts['ocrWhiteboard']
        
        extracted_text = execute_image_completion(
            self.client,
            image_base64,
            ocr_prompt,
            self.model,
            self.vision_temperature
        )
        
        # Post-process the extracted text
        if note_type == "PAPER" or note_type == "WHITEBOARD":
            logger.info("Proofreading text...")
            extracted_text = execute_text_completion(
                self.client,
                extracted_text,
                self.prompts['proofread'],
                self.model,
                self.text_temperature
            )
            
            logger.info("Adding section headers...")
            extracted_text = execute_text_completion(
                self.client,
                extracted_text,
                self.prompts['sectionHeader'],
                self.model,
                self.text_temperature
            )
        
        extracted_text = remove_markdown_code_blocks(extracted_text)
        
        # Extract title
        logger.info("Extracting main title...")
        extracted_title = execute_text_completion(
            self.client,
            extracted_text,
            self.prompts['extractMainTitle'],
            self.model,
            self.text_temperature
        )
        extracted_title = add_datestamp(extracted_title)
        
        return {
            "noteType": note_type,
            "extractedTitle": extracted_title,
            "extractedText": extracted_text
        }

