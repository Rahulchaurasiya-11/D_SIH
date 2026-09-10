"""
Minimal document store with two interchangeable backends.

  * MongoBackend - MongoDB Atlas, used when MONGODB_URI is configured.
  * JsonBackend  - local JSON files, used otherwise.

The JSON backend exists so the system stays fully demonstrable with no network
and no credentials (offline judging, a fresh clone, dead Wi-Fi). Both backends
speak the same small subset of the MongoDB query language, so repository code is
written once and never branches on which backend happens to be live.

Supported filter operators: implicit equality, $eq, $ne, $in, $nin, $gte, $gt,
$lte, $lt, $regex (case-insensitive), $exists, and top-level $or.
"""

import json
import logging
import os
import re
import threading
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("legal_metrology_store")


# --------------------------------------------------------------------------- #
# Query matching (shared semantics for the JSON backend)
# --------------------------------------------------------------------------- #

def _coerce(value: Any) -> Any:
    """Make datetimes comparable with the ISO strings the JSON backend persists."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _match_condition(actual: Any, condition: Any) -> bool:
    if not isinstance(condition, dict) or not any(k.startswith("$") for k in condition):
        return _coerce(actual) == _coerce(condition)

    av = _coerce(actual)
    for op, raw_operand in condition.items():
        operand = _coerce(raw_operand)
        if op == "$eq" and av != operand:
            return False
        if op == "$ne" and av == operand:
            return False
        if op == "$in":
            values = av if isinstance(av, list) else [av]
            if not any(v in operand for v in values):
                return False
        if op == "$nin":
            values = av if isinstance(av, list) else [av]
            if any(v in operand for v in values):
                return False
        if op in ("$gte", "$gt", "$lte", "$lt"):
            if av is None:
                return False
            try:
                if op == "$gte" and not av >= operand:
                    return False
                if op == "$gt" and not av > operand:
                    return False
                if op == "$lte" and not av <= operand:
                    return False
                if op == "$lt" and not av < operand:
                    return False
            except TypeError:
                return False
        if op == "$regex":
            if not isinstance(av, str):
                return False
            try:
                if not re.search(operand, av, re.IGNORECASE):
                    return False
            except re.error:
                # A malformed pattern must not take the endpoint down. Callers are
                # expected to escape user input (see `literal_regex`); this is the
                # backstop for anything that slips through.
                return False
        if op == "$exists":
            if (av is not None) != bool(operand):
                return False
    return True


def matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    for key, condition in (query or {}).items():
        if key == "$or":
            if not any(matches(doc, sub) for sub in condition):
                return False
            continue
        if not _match_condition(doc.get(key), condition):
            return False
    return True


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #

class JsonBackend:
    """File-backed collections. Adequate for demo and single-node deployment."""

    def __init__(self, root: str):
        self.root = root
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._mtimes: Dict[str, float] = {}

    def _path(self, collection: str) -> str:
        return os.path.join(self.root, collection + ".json")

    def _load(self, collection: str) -> List[Dict[str, Any]]:
        path = self._path(collection)

        # Reload when the file changed underneath us. Without this the cache is
        # only correct for a single writer, and anything else touching the store -
        # the seed script, a second worker, an operator editing the file - stays
        # invisible until restart.
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = None

        if collection in self._cache and self._mtimes.get(collection) == mtime:
            return self._cache[collection]

        docs: List[Dict[str, Any]] = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    docs = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read %s (%s); starting that collection empty.", path, exc)
                docs = []
        self._cache[collection] = docs
        self._mtimes[collection] = mtime
        return docs

    def _flush(self, collection: str) -> None:
        path = self._path(collection)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._cache[collection], fh, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
        try:
            self._mtimes[collection] = os.path.getmtime(path)
        except OSError:
            self._mtimes.pop(collection, None)

    def insert(self, collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._load(collection).append(doc)
            self._flush(collection)
            return doc

    def find(self, collection: str, query: Dict[str, Any], sort: Optional[List] = None,
             skip: int = 0, limit: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            results = [d for d in self._load(collection) if matches(d, query)]
        if sort:
            for field, direction in reversed(sort):
                results.sort(
                    key=lambda d: (d.get(field) is None, _coerce(d.get(field))),
                    reverse=direction < 0,
                )
        results = results[skip:]
        return results[:limit] if limit else results

    def count(self, collection: str, query: Dict[str, Any]) -> int:
        with self._lock:
            return sum(1 for d in self._load(collection) if matches(d, query))

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        found = self.find(collection, query, limit=1)
        return found[0] if found else None

    def update_one(self, collection: str, query: Dict[str, Any], changes: Dict[str, Any]) -> bool:
        with self._lock:
            for doc in self._load(collection):
                if matches(doc, query):
                    doc.update(changes)
                    self._flush(collection)
                    return True
        return False

    def delete_one(self, collection: str, query: Dict[str, Any]) -> bool:
        with self._lock:
            docs = self._load(collection)
            for i, doc in enumerate(docs):
                if matches(doc, query):
                    docs.pop(i)
                    self._flush(collection)
                    return True
        return False

    def next_sequence(self, name: str) -> int:
        """Monotonic counter, serialised by the same lock that guards writes."""
        with self._lock:
            docs = self._load("_counters")
            for doc in docs:
                if doc.get("id") == name:
                    doc["value"] = int(doc.get("value", 0)) + 1
                    self._flush("_counters")
                    return doc["value"]
            docs.append({"id": name, "value": 1})
            self._flush("_counters")
            return 1

    def put_blob(self, blob_id: str, data: bytes) -> str:
        blobs = os.path.join(self.root, "blobs")
        os.makedirs(blobs, exist_ok=True)
        with open(os.path.join(blobs, blob_id), "wb") as fh:
            fh.write(data)
        return blob_id

    def get_blob(self, blob_id: str) -> Optional[bytes]:
        path = os.path.join(self.root, "blobs", blob_id)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as fh:
            return fh.read()


class MongoBackend:
    """MongoDB Atlas backend. Filters are pushed down so the indexes get used."""

    def __init__(self, uri: str, db_name: str):
        import gridfs
        import pymongo

        self.client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        self.client.admin.command("ping")
        self.db = self.client.get_database(db_name)
        self.fs = gridfs.GridFS(self.db, collection="evidence")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        import pymongo

        self.db.users.create_index("email", unique=True)
        self.db.inspections.create_index([("created_at", pymongo.DESCENDING)])
        self.db.inspections.create_index("status")
        self.db.inspections.create_index("officer_id")
        self.db.inspections.create_index("violation_rule_ids")
        self.db.inspections.create_index([("brand", pymongo.TEXT), ("product_name", pymongo.TEXT)])
        self.db.audit_log.create_index([("created_at", pymongo.DESCENDING)])

    def insert(self, collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        self.db[collection].insert_one(dict(doc))
        return doc

    def find(self, collection: str, query: Dict[str, Any], sort: Optional[List] = None,
             skip: int = 0, limit: int = 0) -> List[Dict[str, Any]]:
        cursor = self.db[collection].find(query, {"_id": 0})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def count(self, collection: str, query: Dict[str, Any]) -> int:
        return self.db[collection].count_documents(query)

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.db[collection].find_one(query, {"_id": 0})

    def update_one(self, collection: str, query: Dict[str, Any], changes: Dict[str, Any]) -> bool:
        return self.db[collection].update_one(query, {"$set": changes}).matched_count > 0

    def delete_one(self, collection: str, query: Dict[str, Any]) -> bool:
        return self.db[collection].delete_one(query).deleted_count > 0

    def next_sequence(self, name: str) -> int:
        """Atomic server-side increment, so concurrent workers cannot collide."""
        import pymongo

        doc = self.db["_counters"].find_one_and_update(
            {"_id": name},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return int(doc["value"])

    def put_blob(self, blob_id: str, data: bytes) -> str:
        self.fs.put(data, filename=blob_id, _id=blob_id)
        return blob_id

    def get_blob(self, blob_id: str) -> Optional[bytes]:
        try:
            return self.fs.get(blob_id).read()
        except Exception:
            return None


# --------------------------------------------------------------------------- #

_backend = None
_backend_name = "json"


def get_store():
    """Returns the active backend, connecting to Mongo once on first use."""
    global _backend, _backend_name
    if _backend is not None:
        return _backend

    from app.config import settings

    if settings.mongo_enabled:
        try:
            _backend = MongoBackend(settings.MONGODB_URI, settings.MONGODB_DB_NAME)
            _backend_name = "mongodb"
            logger.info("Document store: MongoDB Atlas (%s)", settings.MONGODB_DB_NAME)
            return _backend
        except Exception as exc:
            logger.warning("MongoDB unavailable (%s). Falling back to the local JSON store.", exc)

    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "_store")
    _backend = JsonBackend(root)
    _backend_name = "json"
    logger.info("Document store: local JSON at %s", root)
    return _backend


def backend_name() -> str:
    get_store()
    return _backend_name


def new_id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex[:16]


def literal_regex(text: str, max_length: int = 120) -> str:
    """
    Escapes user input for use as a `$regex` operand.

    Search terms come straight from an officer's keyboard. Unescaped, a bare "["
    is an invalid pattern (500 on the JSON backend) and something like "(a+)+$"
    is a catastrophic-backtracking denial of service against both backends. The
    length cap bounds the work a single query can ask for.
    """
    return re.escape((text or "").strip()[:max_length])
