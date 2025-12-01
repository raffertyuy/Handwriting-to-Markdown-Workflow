"""
OneDrive client using Microsoft Graph API.
Replaces Azure Logic App OneDrive connector functionality.
"""

import logging
import requests
from typing import List, Dict, Optional
import time

logger = logging.getLogger(__name__)


class OneDriveClient:
    """Client for interacting with OneDrive via Microsoft Graph API."""
    
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        """
        Initialize OneDrive client.
        
        Args:
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            refresh_token: OAuth2 refresh token
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.token_expires_at = 0
        
    def _get_access_token(self) -> str:
        """Get or refresh access token."""
        # Check if token is still valid (with 5 minute buffer)
        if self.access_token and time.time() < self.token_expires_at - 300:
            return self.access_token
        
        logger.info("Refreshing access token...")
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token',
            'scope': 'Files.ReadWrite offline_access'
        }
        
        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        expires_in = token_data.get('expires_in', 3600)
        self.token_expires_at = time.time() + expires_in
        
        logger.info("Access token refreshed successfully")
        return self.access_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def _get_drive_path(self, folder_path: str) -> str:
        """Convert folder path to Graph API path."""
        # Remove leading slash if present
        folder_path = folder_path.lstrip('/')
        # Graph API uses /drive/root:/path format
        # Handle empty path (root)
        if not folder_path:
            return "/drive/root"
        return f"/drive/root:/{folder_path}:"
    
    def list_files(self, folder_path: str) -> List[Dict]:
        """
        List files in a OneDrive folder.
        
        Args:
            folder_path: Path to folder (e.g., "Handwritten Notes")
            
        Returns:
            List of file metadata dictionaries
        """
        path = self._get_drive_path(folder_path)
        url = f"{self.GRAPH_API_BASE}{path}/children"
        
        files = []
        while url:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            files.extend(data.get('value', []))
            
            # Check for next page
            url = data.get('@odata.nextLink')
            if url:
                # Remove base URL if present
                url = url.replace(self.GRAPH_API_BASE, '')
        
        return files
    
    def download_file(self, file_path: str) -> bytes:
        """
        Download file from OneDrive.
        
        Args:
            file_path: Path to file (e.g., "Handwritten Notes/image.jpg")
            
        Returns:
            File content as bytes
        """
        path = self._get_drive_path(file_path)
        url = f"{self.GRAPH_API_BASE}{path}/content"
        
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        return response.content
    
    def upload_file(self, file_path: str, content: bytes, content_type: str = None):
        """
        Upload file to OneDrive.
        Creates parent folders if they don't exist.
        
        Args:
            file_path: Destination path (e.g., "second-brain/second-brain/_scans/file.md")
            content: File content as bytes
            content_type: MIME type (e.g., "text/markdown", "image/jpeg")
        """
        # Ensure parent folder exists
        path_parts = file_path.rsplit('/', 1)
        if len(path_parts) == 2:
            parent_folder = path_parts[0]
            file_name = path_parts[1]
            self._ensure_folder_exists(parent_folder)
        else:
            file_name = file_path
        
        path = self._get_drive_path(file_path)
        url = f"{self.GRAPH_API_BASE}{path}/content"
        
        # For file upload, we use PUT with binary content
        headers = {'Authorization': self._get_headers()['Authorization']}
        if content_type:
            headers['Content-Type'] = content_type
        
        response = requests.put(url, headers=headers, data=content)
        response.raise_for_status()
        
        logger.info(f"File uploaded successfully: {file_path}")
    
    def _ensure_folder_exists(self, folder_path: str):
        """Ensure folder exists, creating it if necessary."""
        if not folder_path:
            return
        
        # Check if folder exists
        if self.file_exists(folder_path):
            return
        
        # Create folder recursively
        parts = folder_path.split('/')
        current_path = ""
        for part in parts:
            if not part:
                continue
            if current_path:
                current_path = f"{current_path}/{part}"
            else:
                current_path = part
            
            if not self.file_exists(current_path):
                self._create_folder(current_path)
    
    def _create_folder(self, folder_path: str):
        """Create a folder in OneDrive."""
        path_parts = folder_path.rsplit('/', 1)
        if len(path_parts) == 2:
            parent_path = path_parts[0]
            folder_name = path_parts[1]
        else:
            parent_path = ""
            folder_name = folder_path
        
        parent_path_api = self._get_drive_path(parent_path)
        url = f"{self.GRAPH_API_BASE}{parent_path_api}/children"
        
        payload = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        
        response = requests.post(url, headers=self._get_headers(), json=payload)
        if response.status_code == 409:  # Already exists
            logger.info(f"Folder already exists: {folder_path}")
        else:
            response.raise_for_status()
            logger.info(f"Folder created: {folder_path}")
    
    def move_file(self, source_path: str, dest_path: str):
        """
        Move file from source to destination.
        Creates destination folder if it doesn't exist.
        
        Args:
            source_path: Source file path
            dest_path: Destination file path
        """
        # Ensure destination folder exists
        dest_parts = dest_path.rsplit('/', 1)
        if len(dest_parts) == 2:
            dest_folder = dest_parts[0]
            dest_name = dest_parts[1]
            self._ensure_folder_exists(dest_folder)
        else:
            dest_folder = ""
            dest_name = dest_path
        
        source_path_api = self._get_drive_path(source_path)
        url = f"{self.GRAPH_API_BASE}{source_path_api}"
        
        # Build parent reference path
        if dest_folder:
            parent_path = f"/drive/root:/{dest_folder}"
        else:
            parent_path = "/drive/root"
        
        payload = {
            'parentReference': {
                'path': parent_path
            },
            'name': dest_name
        }
        
        response = requests.patch(url, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        
        logger.info(f"File moved successfully: {source_path} -> {dest_path}")
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in OneDrive.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file exists, False otherwise
        """
        path = self._get_drive_path(file_path)
        url = f"{self.GRAPH_API_BASE}{path}"
        
        response = requests.get(url, headers=self._get_headers())
        return response.status_code == 200

