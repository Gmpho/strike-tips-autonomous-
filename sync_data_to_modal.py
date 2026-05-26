import modal
import shutil
import os
from pathlib import Path

LOCAL_DATA_DIR = Path("data")

app = modal.App("data-sync")
volume = modal.Volume.from_name("strike-tips-data", create_if_missing=True)


@app.function(volumes={"/app/data": volume})
def sync_data():
    """Upload local data/ directory to Modal volume."""
    print("Syncing local data to Modal volume 'strike-tips-data'...")

    for file_path in sorted(LOCAL_DATA_DIR.rglob("*")):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(LOCAL_DATA_DIR)
        dest = f"/app/data/{rel_path}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(file_path, dest)
        print(f"  {rel_path}")

    volume.commit()
    print("Sync complete!")


if __name__ == "__main__":
    with app.run():
        sync_data()
