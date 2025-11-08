"""
https://fnndsc.github.io/ChRIS_ultron_backEnd
"""

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from dateutil import parser as dtparser
from dotenv import load_dotenv

load_dotenv()

USER = os.environ.get("CHRIS_USER", "chris")
LOCK_DIR_PATH = os.environ.get("LOCK_DIR_PATH", "home/chris/locks")
PREEMPT = os.environ.get("PREEMPT", "false").lower() in {"1", "true", "yes"}
SESSION = requests.Session()


def iso_to_dt(iso: str) -> datetime:
    dt = dtparser.isoparse(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def login(api_url, token=None, password=None) -> None:
    if not token:
        r = SESSION.post(
            f"{api_url}/auth-token/",
            json={"username": USER, "password": password},
            timeout=30,
        )
        r.raise_for_status()
        token = r.json()["token"]
    SESSION.headers.update({"Authorization": f"Token {token}"})


# https://chris-api.nidusai.ca/api/v1/userfiles/search/?fname_icontains=home%2Fchris%2Flocks%2F
def list_folder_files(api_url, folder_path: str) -> List[Dict[str, Any]]:
    r = SESSION.get(
        f"{api_url}/userfiles/search/",
        params={"fname_icontains": f"{folder_path}/"},
        headers={"Accept": "application/vnd.collection+json"},
        timeout=60,
    )
    r.raise_for_status()
    items = r.json()["collection"]["items"]
    return [
        {d["name"]: d["value"] for d in it["data"]} | {"url": it["href"]}
        for it in items
    ]


def parse_lock_fname(fname: str) -> Optional[str]:
    fname = fname.split("/")[-1]
    if fname.startswith("lock-") and "T" in fname and fname.endswith("Z"):
        iso = fname[5:]
        try:
            iso_to_dt(iso)
            return iso
        except Exception:
            pass
    return None


def find_current_lock(api_url) -> Optional[dict]:
    files = list_folder_files(api_url, LOCK_DIR_PATH)
    locks = [
        (iso, f)
        for f in files
        if (iso := parse_lock_fname(f.get("fname", "")))
    ]
    return min(locks, key=lambda t: t[0])[1] if locks else None


# https://chris-api.nidusai.ca/api/v1/userfiles/
def upload_file(api_url, upload_path: str, content: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
        tf.write(content)
        tf.flush()
        tmp_path = tf.name

    try:
        with open(tmp_path, "rb") as f:
            r = SESSION.post(
                f"{api_url}/userfiles/",
                files={"fname": (os.path.basename(upload_path), f)},
                data={"upload_path": upload_path},
                timeout=120,
            )
            r.raise_for_status()
    finally:
        os.unlink(tmp_path)


def delete_file(api_url, file_entry: dict) -> None:
    file_id = (
        file_entry.get("id") or file_entry["url"].rstrip("/").split("/")[-1]
    )
    r = SESSION.delete(f"{api_url}/userfiles/{file_id}/", timeout=30)
    r.raise_for_status()


def place_lock(
    api_url, my_iso, job_id=None, timeout_seconds: float = 300.0
) -> None:

    if not job_id:
        job_id = ""
    else:
        job_id += "-"

    my_fname = f"{job_id}lock-{my_iso.replace(':', '')}"
    my_path = f"{LOCK_DIR_PATH}/{my_fname}"

    t_start = time.time()
    last_seen = None

    while True:
        cur = find_current_lock(api_url)

        if cur is None:
            upload_file(api_url, my_path, f"lock for {my_iso}\n".encode())
            print(f"[lock] Placed: {my_fname}")
            return

        cur_fname = cur.get("fname", "")
        if cur_fname.endswith(f"/{my_fname}"):
            print(f"[lock] Already placed: {my_fname}")
            return

        if PREEMPT:
            print(f"[lock] Preempting: {cur_fname}")
            delete_file(api_url, cur)
            time.sleep(0.5)
            continue

        if last_seen != cur_fname:
            last_seen = cur_fname
            t_start = time.time()
            print(f"[lock] Waiting for: {cur_fname}")

        if time.time() - t_start > timeout_seconds:
            raise TimeoutError(f"[lock] Timeout waiting for: {cur_fname}")

        time.sleep(5.0)


def release_lock(api_url, my_iso: str = None, job_id=None) -> None:
    cur = find_current_lock(api_url)
    my_fname = f"lock-{my_iso.replace(':', '')}"

    if not my_iso:
        cur_fname = cur.get("fname", "")
        if job_id in cur_fname:
            delete_file(api_url, cur)
            print(f"[lock] Released: {cur_fname}")
            return True

    if cur:
        cur_fname = cur.get("fname", "")
        if cur_fname.endswith(f"/{my_fname}"):
            delete_file(api_url, cur)
            print(f"[lock] Released: {my_fname}")
        else:
            print(f"[lock] Not our lock, skipping release")
    else:
        print(f"[lock] No lock found")


def main(api, password):
    MY_LOCK_DT = os.environ.get(
        "MY_LOCK_DT",
        (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    )
    login(api, password=password)
    print(f"[main] Acquiring lock: {MY_LOCK_DT} (PREEMPT={PREEMPT})")
    place_lock(api, MY_LOCK_DT)

    print("[main] Running job (30s)...")
    time.sleep(30)

    print("[main] Releasing lock")
    release_lock(api, MY_LOCK_DT)
    print("[main] Done")


if __name__ == "__main__":
    BASE = os.environ.get("CHRIS_BASE", "https://chris-api.nidusai.ca")
    API = f"{BASE.rstrip('/')}/api/v1"
    PASS = os.environ.get("CHRIS_PASS", "password")
    main(API, PASS)
