"""Adapter telematika vendor reefer (cloud-first): terjemahkan format vendor ke bacaan TelemetryReading.

Menambah vendor = tulis subclass VendorAdapter lalu daftarkan di REGISTRY. Validasi bacaan dan
penyimpanan tetap di app/ingest/store.py, sama dengan jalur MQTT.
"""

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class VendorBatch:
    truck_id: str
    device_id: str | None
    readings: list[dict[str, Any]] = field(default_factory=list)


class VendorAdapter:
    name = "base"

    def normalize(self, body: bytes, content_type: str) -> list[VendorBatch]:
        raise NotImplementedError


def _group(rows: list[dict[str, Any]]) -> list[VendorBatch]:
    batches: dict[tuple[str, str | None], VendorBatch] = {}
    for r in rows:
        r = dict(r)
        truck, device = str(r.pop("truck_id")).strip(), r.pop("device_id", None) or None
        batches.setdefault((truck, device), VendorBatch(truck, device)).readings.append(r)
    return list(batches.values())


class GenericJsonAdapter(VendorAdapter):
    """{"readings": [{"truck_id": "...", "device_id": "...", <field TelemetryReading>}, ...]}"""

    name = "generic_json"

    def normalize(self, body, content_type):
        data = json.loads(body)
        return _group(data.get("readings", []))


class GenericCsvAdapter(VendorAdapter):
    """CSV berkepala: truck_id, device_id, ts, temp_c, humidity, ambient_c, door_open, reefer_on, speed_kmh, ..."""

    name = "generic_csv"
    BOOL: ClassVar[set[str]] = {"door_open", "reefer_on"}

    def normalize(self, body, content_type):
        rows = []
        for r in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
            r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k}
            for b in self.BOOL & r.keys():
                r[b] = r[b].lower() in ("1", "true", "ya", "yes")
            rows.append({k: v for k, v in r.items() if v != ""})
        return _group(rows)


REGISTRY: dict[str, VendorAdapter] = {a.name: a for a in (GenericJsonAdapter(), GenericCsvAdapter())}
