
import modal
import os
from pathlib import Path

# Local data directory
LOCAL_DATA_DIR = Path("data")

# Modal Volume definition (must match name in deployment.py)
volume = modal.Volume.from_name("strike-tips-data")

def sync_data():
    """Uploads local /data contents to Modal Volume."""
    app = modal.App("data-sync")
    
    with app.run():
        print(f"📡 Syncing local {LOCAL_DATA_DIR} to Modal volume 'strike-tips-data'...")
        
        # Walk through the local data directory
        for file_path in LOCAL_DATA_DIR.rglob("*"):
            if file_path.is_file():
                # Get the relative path for the volume
                rel_path = file_path.relative_to(LOCAL_DATA_DIR)
                print(f"Uploading {rel_path}...")
                
                # Write to volume
                with open(file_path, "rb") as f:
                    volume.write_file(str(rel_path), f)
        
        volume.commit()
        print("✅ Data synchronization complete!")

if __name__ == "__main__":
    sync_data()
