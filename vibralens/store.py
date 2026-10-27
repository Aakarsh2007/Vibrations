"""Persistence: items (JSON documents in collections) + blobs (files).
Two backends with the same interface:
  * LocalStore  - filesystem (dev, tests, and a no-AWS fallback)
  * AwsStore    - one DynamoDB table (pk = "<collection>#<id>") + one S3 bucket
Both support create-if-absent (idempotency) and versioned read-modify-write (optimistic locking)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import threading
import time
from decimal import Decimal
from pathlib import Path

from . import config


class Conflict(Exception):
    pass


class LocalStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or config.DATA_DIR)
        (self.root / "items").mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.secret = self._secret()

    def _secret(self) -> bytes:
        p = self.root / ".secret"
        if not p.exists():
            p.write_bytes(os.urandom(32))
        return p.read_bytes()

    def _p(self, coll, id_):
        d = self.root / "items" / coll
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{_safe(id_)}.json"

    def get(self, coll, id_):
        p = self._p(coll, id_)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def _write(self, p: Path, item):
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(item, f)
        os.replace(tmp, p)

    def put_new(self, coll, id_, item) -> bool:
        with self._lock:
            p = self._p(coll, id_)
            if p.exists():
                return False
            item = {**item, "version": item.get("version", 0)}
            self._write(p, item)
            return True

    def put(self, coll, id_, item):
        with self._lock:
            self._write(self._p(coll, id_), item)

    def update(self, coll, id_, fn, expect_version=None):
        with self._lock:
            cur = self.get(coll, id_)
            if cur is None:
                raise KeyError(id_)
            if expect_version is not None and cur.get("version", 0) != expect_version:
                raise Conflict(id_)
            new = fn(dict(cur))
            if new is None:
                return cur
            new["version"] = cur.get("version", 0) + 1
            self._write(self._p(coll, id_), new)
            return new

    def list(self, coll, **eq):
        d = self.root / "items" / coll
        out = []
        if d.exists():
            for p in d.glob("*.json"):
                try:
                    it = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if all(it.get(k) == v for k, v in eq.items()):
                    out.append(it)
        return out

    # blobs
    def blob_put_file(self, key, src_path):
        dst = self.root / "blobs" / key
        dst.parent.mkdir(parents=True, exist_ok=True)
        if Path(src_path) != dst:
            import shutil
            shutil.copyfile(src_path, dst)

    def blob_put_bytes(self, key, data: bytes):
        dst = self.root / "blobs" / key
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)

    def blob_exists(self, key) -> int | None:
        p = self.root / "blobs" / key
        return p.stat().st_size if p.exists() else None

    def blob_local_path(self, key) -> str:
        return str(self.root / "blobs" / key)

    def blob_url(self, key, ttl=600) -> str:
        exp = int(time.time()) + ttl
        sig = self.sign(f"get:{key}:{exp}")
        return f"/api/blob?key={key}&exp={exp}&sig={sig}"

    def upload_target(self, key, content_type, max_bytes, ttl=900) -> dict:
        exp = int(time.time()) + ttl
        sig = self.sign(f"put:{key}:{content_type}:{max_bytes}:{exp}")
        return {"method": "PUT", "url": f"/api/local-upload?key={key}&ct={content_type}&max={max_bytes}&exp={exp}&sig={sig}",
                "fields": {}}

    def sign(self, msg: str) -> str:
        return hmac.new(self.secret, msg.encode(), hashlib.sha256).hexdigest()[:40]

    def verify(self, msg: str, sig: str, exp: int) -> bool:
        return exp >= time.time() and hmac.compare_digest(self.sign(msg), sig)


class AwsStore:  # pragma: no cover - exercised on AWS
    def __init__(self):
        import boto3
        self.ddb = boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.TABLE_PREFIX + "items")
        self.s3 = boto3.client("s3", region_name=config.AWS_REGION,
                               endpoint_url=f"https://s3.{config.AWS_REGION}.amazonaws.com")
        self.bucket = config.BUCKET
        self._tmp = Path(tempfile.gettempdir()) / "vl_blobs"

    @staticmethod
    def _enc(item):
        return json.loads(json.dumps(item), parse_float=Decimal)

    @staticmethod
    def _dec(item):
        if item is None:
            return None
        item = dict(item)
        item.pop("pk", None); item.pop("coll", None)
        return json.loads(json.dumps(item, default=lambda d: float(d) if d % 1 else int(d)))

    def get(self, coll, id_):
        r = self.ddb.get_item(Key={"pk": f"{coll}#{id_}"}, ConsistentRead=True)
        return self._dec(r.get("Item"))

    def put_new(self, coll, id_, item) -> bool:
        from botocore.exceptions import ClientError
        try:
            self.ddb.put_item(Item={**self._enc({**item, "version": item.get("version", 0)}), "pk": f"{coll}#{id_}",
                                    "coll": coll}, ConditionExpression="attribute_not_exists(pk)")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def put(self, coll, id_, item):
        self.ddb.put_item(Item={**self._enc(item), "pk": f"{coll}#{id_}", "coll": coll})

    def update(self, coll, id_, fn, expect_version=None):
        from botocore.exceptions import ClientError
        for _ in range(5):
            cur = self.get(coll, id_)
            if cur is None:
                raise KeyError(id_)
            v = cur.get("version", 0)
            if expect_version is not None and v != expect_version:
                raise Conflict(id_)
            new = fn(dict(cur))
            if new is None:
                return cur
            new["version"] = v + 1
            try:
                self.ddb.put_item(Item={**self._enc(new), "pk": f"{coll}#{id_}", "coll": coll},
                                  ConditionExpression="version = :v", ExpressionAttributeValues={":v": v})
                return new
            except ClientError as e:
                if e.response["Error"]["Code"] != "ConditionalCheckFailedException" or expect_version is not None:
                    raise Conflict(id_) from e
        raise Conflict(id_)

    def list(self, coll, **eq):
        from boto3.dynamodb.conditions import Attr
        cond = Attr("coll").eq(coll)
        for k, v in eq.items():
            cond = cond & Attr(k).eq(v)
        out, kw = [], {"FilterExpression": cond}
        while True:  # small tables; a GSI on coll would replace the scan at scale
            r = self.ddb.scan(**kw)
            out += [self._dec(i) for i in r["Items"]]
            if "LastEvaluatedKey" not in r:
                return out
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def blob_put_file(self, key, src_path):
        self.s3.upload_file(str(src_path), self.bucket, key)

    def blob_put_bytes(self, key, data: bytes):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)

    def blob_exists(self, key):
        try:
            return self.s3.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
        except Exception:
            return None

    def blob_local_path(self, key) -> str:
        p = self._tmp / key
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            self.s3.download_file(self.bucket, key, str(p))
        return str(p)

    def blob_url(self, key, ttl=600) -> str:
        return self.s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=ttl)

    def upload_target(self, key, content_type, max_bytes, ttl=900) -> dict:
        r = self.s3.generate_presigned_post(self.bucket, key, Fields={"Content-Type": content_type},
                                            Conditions=[{"Content-Type": content_type},
                                                        ["content-length-range", 1024, max_bytes]], ExpiresIn=ttl)
        return {"method": "POST", "url": r["url"], "fields": r["fields"]}


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(s))


_store = None


def get_store():
    global _store
    if _store is None:
        _store = AwsStore() if config.BACKEND == "aws" else LocalStore()
    return _store
