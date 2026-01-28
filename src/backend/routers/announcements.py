"""
Announcements management endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson.objectid import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "message": doc.get("message"),
        "start_date": (doc.get("start_date").isoformat() if doc.get("start_date") else None),
        "expires_at": (doc.get("expires_at").isoformat() if doc.get("expires_at") else None),
        "created_by": doc.get("created_by"),
        "created_at": (doc.get("created_at").isoformat() if doc.get("created_at") else None),
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return currently active announcements (by start/expiry)."""
    now = datetime.utcnow()
    query = {
        "expires_at": {"$gt": now}
    }
    # start_date can be None or <= now
    docs = announcements_collection.find(query).sort("expires_at", -1)
    results = []
    for d in docs:
        sd = d.get("start_date")
        if sd and sd > now:
            continue
        results.append(serialize(d))
    return results


@router.get("/all", response_model=List[Dict[str, Any]])
def list_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """List all announcements. Requires a signed-in teacher (any role)."""
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    docs = announcements_collection.find({}).sort("expires_at", -1)
    return [serialize(d) for d in docs]


@router.post("", response_model=Dict[str, Any])
def create_announcement(message: str, expires_at: str, teacher_username: Optional[str] = Query(None), start_date: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Create a new announcement. `expires_at` must be an ISO datetime string."""
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expires_at format; use ISO datetime")

    start_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format; use ISO datetime")

    if expires_dt <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    doc = {
        "message": message,
        "start_date": start_dt,
        "expires_at": expires_dt,
        "created_by": teacher_username,
        "created_at": datetime.utcnow(),
    }

    result = announcements_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.put("/{id}")
def update_announcement(id: str, message: Optional[str] = None, expires_at: Optional[str] = None, start_date: Optional[str] = None, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

    update = {}
    if message is not None:
        update["message"] = message
    if expires_at is not None:
        try:
            update["expires_at"] = datetime.fromisoformat(expires_at)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid expires_at format")
    if start_date is not None:
        if start_date == "":
            update["start_date"] = None
        else:
            try:
                update["start_date"] = datetime.fromisoformat(start_date)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid start_date format")

    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = announcements_collection.update_one({"_id": oid}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    doc = announcements_collection.find_one({"_id": oid})
    return serialize(doc)


@router.delete("/{id}")
def delete_announcement(id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Deleted"}
