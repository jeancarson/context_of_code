from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.database import get_db
from lib.models.generated_models import Devices

# List of device UUIDs to insert
device_uuids = [
    "5edcfadf-3d36-4147-bb4a-7e3c2eaaa7e4",
    "a7e6e3e3-b676-4370-954d-5bd654bb63ee",
    "3aca56bc-b023-40c2-aa4b-fbb80b9b95c7"
]

def insert_devices():
    with get_db() as db:
        for uuid_hex in device_uuids:
            # Check if device already exists
            existing = db.query(Devices).filter(Devices.uuid == uuid_hex).first()
            if not existing:
                device = Devices(
                    uuid=uuid_hex,
                    created_at=str(datetime.now())
                )
                db.add(device)
                print(f"Inserted device with UUID: {uuid_hex}")
            else:
                print(f"Device already exists with UUID: {uuid_hex}")
        db.commit()

if __name__ == "__main__":
    insert_devices()
