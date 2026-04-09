import os
import traceback
from typing import Any, Callable, Dict

from pipeline.orchestrator import DubbingOrchestrator

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _set_job_state(
    jobs: Dict[str, Dict[str, Any]],
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    results: Dict[str, Any] | None = None,
) -> None:
    if job_id not in jobs:
        return

    if status is not None:
        jobs[job_id]["status"] = status
    if progress is not None:
        jobs[job_id]["progress"] = round(float(progress), 1)
    if message is not None:
        jobs[job_id]["message"] = message
    if results is not None:
        jobs[job_id]["results"] = results


def _make_progress_callback(job_id: str, jobs: Dict[str, Dict[str, Any]]) -> Callable[[float, str], None]:
    def callback(progress: float, message: str) -> None:
        _set_job_state(jobs, job_id, status="processing", progress=progress, message=message)

    return callback


def _to_public_url(path: str | None, base_url: str) -> str | None:
    if not path:
        return None

    abs_path = os.path.abspath(path)
    try:
        rel_path = os.path.relpath(abs_path, BASE_DIR)
    except ValueError:
        return None

    rel_path = rel_path.replace(os.sep, "/")
    if rel_path.startswith("outputs/") or rel_path.startswith("uploads/"):
        return f"{base_url}/{rel_path}"
    return None


def process_video_job(job_id: str, file_path: str, target_language: str, jobs: Dict[str, Dict[str, Any]]) -> None:
    base_url = os.getenv("PUBLIC_BACKEND_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
    output_dir = os.path.join(BASE_DIR, "outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        _set_job_state(
            jobs,
            job_id,
            status="processing",
            progress=5.0,
            message=f"Preparing {target_language} dubbing pipeline...",
        )

        orchestrator = DubbingOrchestrator(
            input_path=file_path,
            target_lang=target_language,
            output_dir=output_dir,
            progress_callback=_make_progress_callback(job_id, jobs),
        )
        result = orchestrator.run()

        artifacts = result.get("artifacts", {})
        payload = {
            "original": _to_public_url(file_path, base_url),
            "dubbed": _to_public_url(artifacts.get("dubbed_video"), base_url),
            "source_audio": _to_public_url(artifacts.get("source_audio"), base_url),
            "dubbed_audio": _to_public_url(artifacts.get("dubbed_audio"), base_url),
            "raw_dubbed_audio": _to_public_url(artifacts.get("dubbed_audio_raw"), base_url),
            "plot_url": _to_public_url(artifacts.get("comparison_plot"), base_url),
            "metrics_url": _to_public_url(artifacts.get("results_json"), base_url),
            "manifest_url": _to_public_url(artifacts.get("segment_manifest"), base_url),
            "run_summary_url": _to_public_url(artifacts.get("run_summary"), base_url),
            "transcription_url": _to_public_url(artifacts.get("transcription"), base_url),
            "translation_url": _to_public_url(artifacts.get("translation"), base_url),
            "metrics": result.get("metrics"),
            "run_validity": result.get("run_validity"),
            "source_type": result.get("source_type"),
            "target_language": target_language,
            "summary": result.get("summary"),
            "transcription_text": result.get("transcription_text"),
            "translation_text": result.get("translation_text"),
            "artifacts": {
                key: _to_public_url(value, base_url) if isinstance(value, str) else value
                for key, value in artifacts.items()
            },
        }

        _set_job_state(
            jobs,
            job_id,
            status="completed",
            progress=100.0,
            message=f"{target_language} dubbing complete.",
            results=payload,
        )
    except Exception as exc:
        traceback.print_exc()
        message = str(exc)
        if "audio" in message.lower():
            message = (
                f"{message} Try a video with clear spoken audio, or use the built-in demo clip for the presentation."
            )
        _set_job_state(
            jobs,
            job_id,
            status="failed",
            progress=100.0,
            message=f"Pipeline failed: {message}",
            results={"error": message},
        )
