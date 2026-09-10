import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st
import yt_dlp

VIDEOS = [
    "jNQXAC9IVRw",
    "aqz-KE-bpKQ",
    "M7lc1UVf-VE",
]
ROOT = Path("/tmp/streamlit-ytdlp-smoke")


def run_command(args, timeout=240):
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "exit": completed.returncode,
            "elapsed": round(time.perf_counter() - started, 2),
            "log": (completed.stdout + "\n" + completed.stderr).strip(),
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return {
            "exit": 124,
            "elapsed": round(time.perf_counter() - started, 2),
            "log": output.strip() + "\nTIMEOUT",
        }


def flags(log):
    lowered = log.lower()
    return {
        "bot_signin": "sign in to confirm" in lowered or "not a bot" in lowered,
        "http_403": "http error 403" in lowered or "http 403" in lowered,
        "challenge": "challenge" in lowered,
    }


def run_smoke():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)

    common = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--ignore-config",
        "--no-playlist",
        "--js-runtimes",
        "deno",
    ]
    results = []

    for video_id in VIDEOS:
        url = "https://www.youtube.com/watch?v=" + video_id
        target = ROOT / video_id
        target.mkdir()

        metadata = run_command(
            common
            + [
                "--skip-download",
                "--print",
                "%(id)s|%(title)s|%(duration)s",
                url,
            ]
        )
        download = run_command(
            common
            + [
                "-f",
                "worst",
                "-o",
                str(target / "%(id)s.%(ext)s"),
                url,
            ]
        )
        files = [
            {"path": str(path), "size": path.stat().st_size}
            for path in target.iterdir()
            if path.is_file()
        ]
        combined_log = metadata["log"] + "\n" + download["log"]
        results.append(
            {
                "video_id": video_id,
                "metadata_success": metadata["exit"] == 0,
                "metadata_elapsed": metadata["elapsed"],
                "download_success": download["exit"] == 0 and bool(files),
                "download_elapsed": download["elapsed"],
                "files": files,
                **flags(combined_log),
                "metadata_exit": metadata["exit"],
                "download_exit": download["exit"],
                "metadata_log": metadata["log"][-5000:],
                "download_log": download["log"][-5000:],
            }
        )
    return results


st.title("Streamlit Community Cloud yt-dlp smoke")
st.caption("No cookies, YouTube login, proxy/VPN, WARP, or PO Token provider.")

deno_version = run_command(["deno", "--version"], timeout=20)
st.json(
    {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "yt_dlp": yt_dlp.version.__version__,
        "deno": deno_version["log"].splitlines()[0] if deno_version["exit"] == 0 else "unavailable",
    }
)

if st.button("Run 3-video smoke", type="primary"):
    with st.spinner("Testing metadata and real media downloads..."):
        st.session_state["results"] = run_smoke()

if "results" in st.session_state:
    results = st.session_state["results"]
    summary = [
        {
            "video_id": item["video_id"],
            "metadata": item["metadata_success"],
            "metadata_s": item["metadata_elapsed"],
            "download": item["download_success"],
            "download_s": item["download_elapsed"],
            "file_count": len(item["files"]),
            "file_bytes": sum(file["size"] for file in item["files"]),
            "bot_signin": item["bot_signin"],
            "http_403": item["http_403"],
            "challenge": item["challenge"],
        }
        for item in results
    ]
    st.dataframe(summary, use_container_width=True)
    st.code(json.dumps(results, ensure_ascii=False, indent=2))
