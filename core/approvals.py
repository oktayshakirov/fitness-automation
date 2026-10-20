"""Version-bound human review records. Call record_review only after explicit review.
The caller must validate current_asset before granting approval.
"""
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(entry):
    return {"spec_sha256": entry["spec_sha256"],
            "pipeline_sha256": entry["pipeline_sha256"],
            "media_sha256": hashlib.sha256(json.dumps(entry.get("media", {}), sort_keys=True).encode()).hexdigest()}


def is_approved(eid, entry, root=None):
    """The entry must already have passed current_asset validation."""
    root = Path(root or ROOT)
    try:
        record = json.loads((root / "approvals" / (eid + ".json")).read_text())
        cat = json.loads((root / "catalog" / (eid + ".json")).read_text())
        motion = json.loads((root / "motion/specs" / (eid + ".json")).read_text())
        return bool(cat.get("reviewed") and motion.get("approved") and
                    record.get("approved") and record.get("fingerprint") == fingerprint(entry))
    except (OSError, ValueError, KeyError):
        return False


def record_review(eid, approved, entry, reason, root=None):
    root = Path(root or ROOT)
    if not re.fullmatch(r"[a-z0-9_]+", eid) or type(approved) is not bool or not reason.strip():
        raise ValueError("Valid exercise ID, boolean approval and review note required")
    record = {"id": eid, "approved": approved,
              "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "note": reason, "fingerprint": fingerprint(entry) if approved else None}
    # Read both files before any writes; missing pairs must not create partial approval.
    pairs = [(root / folder / (eid + ".json"), flag)
             for folder, flag in [("catalog", "reviewed"), ("motion/specs", "approved")]]
    values = [(p, flag, json.loads(p.read_text())) for p, flag in pairs]
    for p, flag, value in values:
        value[flag] = approved
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(value, indent=2) + "\n")
        tmp.replace(p)
    folder = root / "approvals"
    folder.mkdir(exist_ok=True)
    tmp = folder / (eid + ".json.tmp")
    tmp.write_text(json.dumps(record, indent=2) + "\n")
    tmp.replace(folder / (eid + ".json"))
    with (folder / "history.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    asset = root / "dist" / eid / "asset.json"
    if asset.exists():
        value = json.loads(asset.read_text())
        value["approved"] = approved
        tmp = asset.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(value, indent=2) + "\n")
        tmp.replace(asset)
    return record
