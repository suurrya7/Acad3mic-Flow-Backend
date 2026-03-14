#!/usr/bin/env python3
"""
Storage Bucket Setup Script
Run this to create the required Supabase storage bucket for document uploads.
"""

from app.db.supabase import get_supabase_admin
from app.utils.logger import logger

def create_storage_bucket():
    """Create the 'assignments' storage bucket if it doesn't exist"""
    supabase = get_supabase_admin()
    
    try:
        # Attempt to create the bucket
        bucket_config = {
            "public": False,
            "file_size_limit": 10485760,  # 10MB
            "allowed_mime_types": ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"]
        }
        
        supabase.storage.create_bucket("assignments", bucket_config)
        logger.info("✓ Successfully created 'assignments' storage bucket")
        print("✓ Successfully created 'assignments' storage bucket")
        
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
            logger.info("✓ Storage bucket 'assignments' already exists")
            print("✓ Storage bucket 'assignments' already exists")
        else:
            logger.error(f"✗ Failed to create storage bucket: {error_msg}")
            print(f"✗ Failed to create storage bucket: {error_msg}")
            raise

if __name__ == "__main__":
    print("Setting up Supabase storage bucket...")
    create_storage_bucket()
    print("\nSetup complete!")
