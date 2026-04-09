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
        supabase.storage.create_bucket(
            id="assignments",
            options={
                "public": False,
                "file_size_limit": 10485760,  # 10MB
                "allowed_mime_types": [
                    "application/pdf", 
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                    "application/msword",
                    "text/plain",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.ms-excel"
                ]
            }
        )
        logger.info("✓ Successfully created 'assignments' storage bucket")
        print("✓ Successfully created 'assignments' storage bucket")
        
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
            try:
                # If it exists, update it to ensure settings are correct
                supabase.storage.update_bucket(
                    id="assignments",
                    options={
                        "public": False,
                        "file_size_limit": 10485760,
                        "allowed_mime_types": [
                            "application/pdf", 
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                            "application/msword",
                            "text/plain",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "application/vnd.ms-excel"
                        ]
                    }
                )
                logger.info("✓ Successfully updated 'assignments' storage bucket configuration")
                print("✓ Successfully updated 'assignments' storage bucket configuration")
            except Exception as update_err:
                logger.error(f"✗ Failed to update existing storage bucket: {str(update_err)}")
                print(f"✗ Failed to update existing storage bucket: {str(update_err)}")
        else:
            logger.error(f"✗ Failed to create storage bucket: {error_msg}")
            print(f"✗ Failed to create storage bucket: {error_msg}")
            raise

if __name__ == "__main__":
    print("Setting up Supabase storage bucket...")
    create_storage_bucket()
    print("\nSetup complete!")
