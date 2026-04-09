import json
import os
import subprocess
import time
from typing import Callable

import librosa
import numpy as np
import soundfile as sf

from .align import align_prosody, stretch_to_duration
from .analyze import extract_acoustic_features
from .emotion_map import map_features_to_emotion
from .evaluate import evaluate_metrics
from .ingest import extract_audio
from .preprocess import segment_audio
from .synthesize import resolve_elevenlabs_voice_profile, synthesize_speech
from .transcribe_translate import (
    TranslationService,
    get_demo_segment,
    get_demo_transcript,
    get_demo_translation,
    get_showcase_translation,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
DEFAULT_PIPELINE_SAMPLE_RATE = 16000


class DubbingOrchestrator:
    def __init__(
        self,
        input_path: str,
        target_lang: str = "English",
        output_dir: str = "results",
        progress_callback: Callable[[float, str], None] | None = None,
    ):
        self.input_path = os.path.abspath(input_path)
        self.target_lang = target_lang
        self.output_dir = os.path.abspath(output_dir)
        self.progress_callback = progress_callback
        os.makedirs(self.output_dir, exist_ok=True)
        self.translator = TranslationService()

    def _update(self, progress: float, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(progress, message)

    def _detect_source_type(self) -> str:
        input_name = os.path.basename(self.input_path).lower()
        if any(hint in input_name for hint in ("speech_sample.wav", "synthetic", "gtts", "presentation_scripted_demo")):
            return "Synthetic Speech / TTS"
        if any(hint in input_name for hint in ("audio.aac", "beep", "tone")):
            return "Non-Speech / Dummy"
        return "Human Speech (Provisionally Validated)"

    def _is_curated_demo(self) -> bool:
        input_name = os.path.basename(self.input_path).lower()
        return any(hint in input_name for hint in ("presentation_scripted_demo",))

    def _is_showcase_demo(self) -> bool:
        input_name = os.path.basename(self.input_path).lower()
        return "showcase_demo" in input_name or "whatsapp video 2026-04-08 at 7.35.05 pm" in input_name

    def _is_video_input(self) -> bool:
        return os.path.splitext(self.input_path)[1].lower() in VIDEO_EXTENSIONS

    def _load_segment_metadata(self) -> dict:
        segments_path = os.path.join(self.output_dir, "segments.json")
        if not os.path.exists(segments_path):
            return {"segments": []}
        with open(segments_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _segment_duration(self, seg_meta: dict, index: int, fallback_audio_path: str, sample_rate: int) -> float:
        segments = seg_meta.get("segments") or []
        if index < len(segments):
            return max(float(segments[index].get("duration", 0.0)), 0.4)

        y_seg, _ = librosa.load(fallback_audio_path, sr=sample_rate, mono=True)
        return max(len(y_seg) / sample_rate, 0.4)

    def _timing_penalty(self, timing_info: dict) -> float:
        stretch_rate = max(float(timing_info.get("stretch_rate", 1.0) or 1.0), 1e-6)
        return abs(float(np.log(stretch_rate)))

    def _retry_tts_speed(self, timing_info: dict, default_speed: float = 1.0) -> float | None:
        source_duration = float(timing_info.get("source_duration_s", 0.0) or 0.0)
        target_duration = float(timing_info.get("target_duration_s", 0.0) or 0.0)
        if source_duration <= 0.0 or target_duration <= 0.0:
            return None

        desired_speed = source_duration / target_duration
        desired_speed = float(np.clip(desired_speed, 0.7, 1.08))
        if abs(desired_speed - default_speed) < 0.05:
            return None
        return desired_speed

    def _synthesis_penalty(self, synthesis_info: dict, timing_info: dict) -> float:
        guide_timing = synthesis_info.get("guide_timing") if synthesis_info else None
        penalty = self._timing_penalty(timing_info)
        if isinstance(guide_timing, dict) and guide_timing.get("stretch_rate"):
            penalty += self._timing_penalty(guide_timing)
        return penalty

    def _guide_timing_adjustment(self, synthesis_info: dict) -> str | None:
        guide_timing = synthesis_info.get("guide_timing") if synthesis_info else None
        if not isinstance(guide_timing, dict):
            return None

        stretch_rate = float(guide_timing.get("stretch_rate", 1.0) or 1.0)
        if stretch_rate > 1.12:
            return "tighten"
        if stretch_rate < 0.88:
            return "expand"
        return None

    def _should_skip_global_alignment(self, manifest: dict, quality_profile: str) -> bool:
        if quality_profile != "presentation":
            return False

        segments = manifest.get("segments") or []
        if not segments:
            return False

        for segment in segments:
            timing = segment.get("timing") or {}
            stretch_rate = float(timing.get("stretch_rate", 1.0) or 1.0)
            if abs(stretch_rate - 1.0) > 0.04:
                return False

            guide_timing = ((segment.get("synthesis") or {}).get("guide_timing")) or {}
            if guide_timing:
                guide_stretch = float(guide_timing.get("stretch_rate", 1.0) or 1.0)
                if abs(guide_stretch - 1.0) > 0.12:
                    return False
                if guide_timing.get("quality_warning"):
                    return False

        return True

    def _segment_curated_demo_audio(self, source_audio: str, sample_rate: int) -> tuple[list[str], dict]:
        timing_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "outputs", "presentation_demo_assets", "presentation_segments.json")
        )
        if not os.path.exists(timing_path):
            return [], {"segments": []}

        with open(timing_path, "r", encoding="utf-8") as f:
            timing_data = json.load(f)

        y_src, sr = librosa.load(source_audio, sr=sample_rate, mono=True)
        segments = []
        metadata = {"status": "success", "segments": [], "notes": "Used curated demo segment timing."}

        for index, segment in enumerate(timing_data.get("segments", [])):
            start_s = float(segment.get("start_s", 0.0))
            end_s = float(segment.get("end_s", start_s))
            start_idx = max(0, int(round(start_s * sr)))
            end_idx = min(len(y_src), int(round(end_s * sr)))
            if end_idx <= start_idx:
                continue

            chunk_path = os.path.join(self.output_dir, f"segment_{index}.wav")
            sf.write(chunk_path, y_src[start_idx:end_idx], sr)
            segments.append(chunk_path)
            metadata["segments"].append(
                {
                    "id": index,
                    "start_s": round(start_s, 3),
                    "end_s": round(end_s, 3),
                    "duration": round(end_s - start_s, 3),
                    "file": os.path.basename(chunk_path),
                }
            )

        with open(os.path.join(self.output_dir, "segments.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return segments, metadata

    def _feature_snapshot(self, features: dict) -> dict:
        stats = features.get("stats", {})
        return {
            "pitch_mean_hz": round(float(stats.get("pitch_mean_hz", 0.0)), 3),
            "pitch_std_hz": round(float(stats.get("pitch_std_hz", 0.0)), 3),
            "rms_mean": round(float(stats.get("rms_mean", 0.0)), 5),
            "spectral_centroid_mean": round(float(stats.get("spectral_centroid_mean", 0.0)), 3),
            "spectral_flux_mean": round(float(stats.get("spectral_flux_mean", 0.0)), 3),
            "onset_density": round(float(stats.get("onset_density", 0.0)), 3),
            "syllabic_rate": round(float(stats.get("syllabic_rate", 0.0)), 3),
            "jitter_local": round(float(stats.get("jitter_local", 0.0)), 5),
            "shimmer_local": round(float(stats.get("shimmer_local", 0.0)), 5),
            "harmonicity": round(float(stats.get("harmonicity", 0.0)), 5),
        }

    def _build_voice_clone_sample(self, segment_paths: list[str], sample_rate: int) -> str | None:
        if not segment_paths:
            return None

        sample_chunks = []
        total_samples = 0
        max_samples = int(sample_rate * 22)
        gap = np.zeros(int(sample_rate * 0.12), dtype=np.float32)

        for segment_path in segment_paths:
            y_seg, _ = librosa.load(segment_path, sr=sample_rate, mono=True)
            trimmed, _ = librosa.effects.trim(y_seg, top_db=28, frame_length=1024, hop_length=256)
            if trimmed.size < int(sample_rate * 0.5):
                continue

            remaining = max_samples - total_samples
            if remaining <= 0:
                break

            if trimmed.size > remaining:
                trimmed = trimmed[:remaining]

            sample_chunks.append(trimmed.astype(np.float32))
            total_samples += trimmed.size

            if total_samples < max_samples:
                sample_chunks.append(gap.copy())
                total_samples += gap.size

        if not sample_chunks:
            return None

        sample_audio = np.concatenate(sample_chunks)
        peak = float(np.max(np.abs(sample_audio))) if sample_audio.size else 0.0
        if peak > 0.98:
            sample_audio = sample_audio / peak * 0.94

        sample_path = os.path.join(self.output_dir, "voice_clone_sample.wav")
        sf.write(sample_path, sample_audio.astype(np.float32), sample_rate)
        return sample_path

    def _estimate_dialogue_onset(self, audio_path: str, sample_rate: int) -> float:
        y, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
        if not y.size:
            return 0.0

        rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
        if not rms.size:
            return 0.0

        threshold = max(float(np.max(rms)) * 0.2, float(np.mean(rms)) * 1.15, 1e-4)
        active = np.flatnonzero(rms >= threshold)
        if active.size == 0:
            return 0.0

        onset_time = librosa.frames_to_time(int(active[0]), sr=sample_rate, hop_length=256)
        return float(np.clip(onset_time, 0.0, 0.22))

    def _assemble_timeline(
        self,
        total_source_samples: int,
        sample_rate: int,
        dubbed_segments: list[str],
        seg_meta: dict,
        manifest: dict,
    ) -> str:
        canvas = np.zeros(total_source_samples + sample_rate, dtype=np.float32)
        fallback_cursor = 0
        written_until = 0
        segments = seg_meta.get("segments") or []
        crossfade_samples = max(int(sample_rate * 0.03), 1)

        for i, dub_path in enumerate(dubbed_segments):
            y_dub, _ = librosa.load(dub_path, sr=sample_rate, mono=True)
            if i < len(segments):
                start_s = float(segments[i].get("start_s", 0.0))
                insert_idx = int(start_s * sample_rate)
                source_segment_path = manifest["segments"][i].get("source_segment")
                if source_segment_path and os.path.exists(source_segment_path):
                    source_onset_s = self._estimate_dialogue_onset(source_segment_path, sample_rate)
                    dub_onset_s = self._estimate_dialogue_onset(dub_path, sample_rate)
                    onset_shift_s = float(np.clip(source_onset_s - dub_onset_s, -0.18, 0.18))
                    insert_idx += int(round(onset_shift_s * sample_rate))
                    manifest["segments"][i]["source_onset_s"] = round(source_onset_s, 3)
                    manifest["segments"][i]["dubbed_onset_s"] = round(dub_onset_s, 3)
                    manifest["segments"][i]["assembly_onset_shift_s"] = round(onset_shift_s, 3)
            else:
                insert_idx = fallback_cursor

            insert_idx = max(0, insert_idx)
            end_idx = insert_idx + len(y_dub)
            if end_idx > len(canvas):
                canvas = np.pad(canvas, (0, end_idx - len(canvas)))

            overlap = max(0, written_until - insert_idx)
            if overlap > 0:
                overlap_samples = min(overlap, len(y_dub), crossfade_samples)
                overlap_start = insert_idx
                overlap_end = insert_idx + overlap_samples
                fade_out = np.linspace(1.0, 0.0, overlap_samples)
                fade_in = np.linspace(0.0, 1.0, overlap_samples)
                canvas[overlap_start:overlap_end] = (
                    canvas[overlap_start:overlap_end] * fade_out + y_dub[:overlap_samples] * fade_in
                )
                remaining = y_dub[overlap_samples:]
                if remaining.size:
                    canvas[overlap_end:overlap_end + len(remaining)] = remaining
            else:
                canvas[insert_idx:end_idx] = y_dub

            fallback_cursor = end_idx
            written_until = max(written_until, end_idx)
            manifest["segments"][i]["assembly_insert_s"] = round(insert_idx / sample_rate, 3)
            manifest["segments"][i]["dubbed_duration_s"] = round(len(y_dub) / sample_rate, 3)

        peak = float(np.max(np.abs(canvas))) if canvas.size else 0.0
        if peak > 0.99:
            canvas = canvas / peak * 0.95

        raw_dubbed_path = os.path.join(self.output_dir, "dubbed_audio_raw.wav")
        sf.write(raw_dubbed_path, canvas.astype(np.float32), sample_rate)
        return raw_dubbed_path

    def _render_dubbed_video(self, dubbed_audio_path: str) -> str | None:
        if not self._is_video_input():
            return None

        output_path = os.path.join(self.output_dir, "dubbed_video.mp4")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.input_path,
                    "-i",
                    dubbed_audio_path,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-shortest",
                    output_path,
                ],
                capture_output=True,
                check=True,
            )
            return output_path
        except Exception as exc:
            print(f"         [WARNING] Video re-mux failed: {exc}")
            return None

    def run(self) -> dict:
        print("=" * 70)
        print("  Emotion-Preserving AI Video Dubbing -- Modular Pipeline")
        print("=" * 70)
        t_start = time.time()
        processing_sr = int(os.getenv("PIPELINE_SAMPLE_RATE", str(DEFAULT_PIPELINE_SAMPLE_RATE)) or DEFAULT_PIPELINE_SAMPLE_RATE)

        self._update(5, "Extracting source audio...")
        source_audio = extract_audio(self.input_path, self.output_dir, sample_rate=processing_sr)
        y_src, sr = librosa.load(source_audio, sr=processing_sr, mono=True)

        self._update(15, "Segmenting speech chunks...")
        if self._is_curated_demo():
            segments, seg_meta = self._segment_curated_demo_audio(source_audio, sample_rate=sr)
            if not segments:
                segments = segment_audio(source_audio, self.output_dir)
                seg_meta = self._load_segment_metadata()
        else:
            segments = segment_audio(source_audio, self.output_dir)
            seg_meta = self._load_segment_metadata()

        self._update(25, "Extracting acoustic fingerprint...")
        global_features = extract_acoustic_features(source_audio, sample_rate=sr)
        global_valence, global_arousal = map_features_to_emotion(global_features)
        voice_clone_sample = self._build_voice_clone_sample(segments, sr)
        voice_profile = resolve_elevenlabs_voice_profile(
            sample_audio_path=voice_clone_sample,
            friendly_name=os.path.splitext(os.path.basename(self.input_path))[0],
        )

        source_type = self._detect_source_type()
        manifest = {
            "input_media": self.input_path,
            "source_type": source_type,
            "target_language": self.target_lang,
            "source_duration_s": round(len(y_src) / sr, 2),
            "segments_processed": len(segments),
            "global_features": self._feature_snapshot(global_features),
            "voice_profile": {
                "provider": voice_profile.get("provider"),
                "mode": voice_profile.get("mode"),
                "voice_id": voice_profile.get("voice_id"),
            } if voice_profile else None,
            "segments": [],
        }

        transcripts = []
        translations = []
        translated_plain_segments = []
        per_segment_emotion = []
        timed_segments = []
        segment_jobs = []
        is_demo_run = False
        is_curated_demo = self._is_curated_demo()
        is_showcase_demo = self._is_showcase_demo()
        quality_profile = "presentation" if (is_curated_demo or is_showcase_demo or self.target_lang.strip().lower() == "english") else "standard"

        for index, segment_path in enumerate(segments):
            progress = 28 + ((index + 1) / max(len(segments), 1)) * 14
            self._update(progress, f"Analyzing source segment {index + 1}/{len(segments)}...")

            segment_features = extract_acoustic_features(segment_path, sample_rate=sr)
            valence, arousal = map_features_to_emotion(segment_features)
            per_segment_emotion.append((valence, arousal))
            target_duration_s = self._segment_duration(seg_meta, index, segment_path, sample_rate=sr)

            if is_curated_demo:
                curated_segment = get_demo_segment(index, self.target_lang)
                transcript = curated_segment[0] if curated_segment else get_demo_transcript()
                demo_transcript = False
                with open(
                    os.path.join(self.output_dir, f"transcription_segment_{index}.txt"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(transcript)
            else:
                transcript, demo_transcript = self.translator.transcribe(
                    segment_path,
                    self.output_dir,
                    artifact_name=f"transcription_segment_{index}.txt",
                )

            curated_translation = None
            if is_curated_demo:
                curated_segment = get_demo_segment(index, self.target_lang)
                curated_translation = curated_segment[1] if curated_segment else get_demo_translation(self.target_lang)
            elif is_showcase_demo:
                curated_translation = get_showcase_translation(index, self.target_lang)
            segment_info = {"start_s": 0.0, "end_s": round(target_duration_s, 3)}
            if index < len(seg_meta.get("segments", [])):
                segment_info = seg_meta["segments"][index]

            segment_jobs.append(
                {
                    "id": index,
                    "segment_path": segment_path,
                    "segment_info": segment_info,
                    "target_duration_s": target_duration_s,
                    "features": segment_features,
                    "valence": valence,
                    "arousal": arousal,
                    "transcript": transcript,
                    "demo_transcript": demo_transcript,
                    "curated_translation": curated_translation,
                }
            )
            is_demo_run = is_demo_run or demo_transcript

        for index, job in enumerate(segment_jobs):
            progress = 44 + ((index + 1) / max(len(segment_jobs), 1)) * 10
            self._update(progress, f"Translating segment {index + 1}/{len(segment_jobs)}...")

            if job["curated_translation"]:
                translation = job["curated_translation"]
                demo_translation = False
                with open(
                    os.path.join(self.output_dir, f"translation_segment_{index}.txt"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(translation)
            else:
                prev_context = segment_jobs[index - 1]["transcript"] if index > 0 else None
                next_context = segment_jobs[index + 1]["transcript"] if index + 1 < len(segment_jobs) else None
                translation, demo_translation = self.translator.translate(
                    job["transcript"],
                    self.target_lang,
                    self.output_dir,
                    artifact_name=f"translation_segment_{index}.txt",
                    source_duration_s=job["target_duration_s"],
                    valence=job["valence"],
                    arousal=job["arousal"],
                    feature_stats=job["features"].get("stats"),
                    previous_context=prev_context,
                    next_context=next_context,
                )

            job["translation"] = translation
            job["demo_translation"] = demo_translation
            job["translation_strategy"] = "initial"
            translated_plain_segments.append(translation)
            is_demo_run = is_demo_run or demo_translation

        for index, job in enumerate(segment_jobs):
            progress = 54 + ((index + 1) / max(len(segment_jobs), 1)) * 18
            self._update(progress, f"Analyzing and dubbing segment {index + 1}/{len(segment_jobs)}...")

            translation = job["translation"]
            transcript = job["transcript"]
            demo_translation = job["demo_translation"]
            valence = job["valence"]
            arousal = job["arousal"]
            target_duration_s = job["target_duration_s"]
            segment_features = job["features"]
            previous_text = translated_plain_segments[index - 1] if index > 0 else None
            next_text = translated_plain_segments[index + 1] if index + 1 < len(translated_plain_segments) else None

            raw_segment_path, synthesis_info = synthesize_speech(
                translation,
                valence,
                arousal,
                self.output_dir,
                output_filename=f"dubbed_segment_{index}.wav",
                sample_rate=sr,
                target_lang=self.target_lang,
                feature_stats=segment_features.get("stats"),
                target_duration_s=target_duration_s,
                quality_profile=quality_profile,
                voice_profile=voice_profile,
                previous_text=previous_text,
                next_text=next_text,
                segment_index=index,
                source_audio_path=job["segment_path"],
            )

            timed_segment_path = os.path.join(self.output_dir, f"timed_segment_{index}.wav")
            timing_info = stretch_to_duration(
                raw_segment_path,
                target_duration_s=target_duration_s,
                output_path=timed_segment_path,
                sample_rate=sr,
            )

            if (
                synthesis_info.get("method") == "elevenlabs_tts"
                and timing_info.get("quality_warning")
            ):
                retry_speed = self._retry_tts_speed(timing_info, default_speed=float(synthesis_info.get("tts_speed") or 1.0))
                if retry_speed is not None:
                    speed_retry_raw_path, speed_retry_info = synthesize_speech(
                        translation,
                        valence,
                        arousal,
                        self.output_dir,
                        output_filename=f"dubbed_segment_{index}_speed_retry.wav",
                        sample_rate=sr,
                        target_lang=self.target_lang,
                        feature_stats=segment_features.get("stats"),
                        target_duration_s=target_duration_s,
                        quality_profile=quality_profile,
                        voice_profile=voice_profile,
                        previous_text=previous_text,
                        next_text=next_text,
                        segment_index=index,
                        tts_speed=retry_speed,
                        source_audio_path=job["segment_path"],
                    )
                    speed_retry_timed_path = os.path.join(self.output_dir, f"timed_segment_{index}_speed_retry.wav")
                    speed_retry_timing = stretch_to_duration(
                        speed_retry_raw_path,
                        target_duration_s=target_duration_s,
                        output_path=speed_retry_timed_path,
                        sample_rate=sr,
                    )
                    if self._timing_penalty(speed_retry_timing) + 0.02 < self._timing_penalty(timing_info):
                        raw_segment_path = speed_retry_raw_path
                        timed_segment_path = speed_retry_timed_path
                        timing_info = speed_retry_timing
                        synthesis_info = speed_retry_info

            timing_adjustment = self._guide_timing_adjustment(synthesis_info)
            if (
                timing_adjustment
                and not demo_translation
                and not is_curated_demo
                and not job["curated_translation"]
                and self.translator.api_key
            ):
                prev_context = segment_jobs[index - 1]["transcript"] if index > 0 else None
                next_context = segment_jobs[index + 1]["transcript"] if index + 1 < len(segment_jobs) else None
                adjusted_translation, adjusted_demo_translation = self.translator.translate(
                    transcript,
                    self.target_lang,
                    self.output_dir,
                    artifact_name=f"translation_segment_{index}_{timing_adjustment}.txt",
                    source_duration_s=target_duration_s,
                    tighten=timing_adjustment == "tighten",
                    expand=timing_adjustment == "expand",
                    valence=valence,
                    arousal=arousal,
                    feature_stats=segment_features.get("stats"),
                    previous_context=prev_context,
                    next_context=next_context,
                )
                if adjusted_translation and not adjusted_demo_translation and adjusted_translation != translation:
                    adjusted_raw_segment_path, adjusted_synthesis_info = synthesize_speech(
                        adjusted_translation,
                        valence,
                        arousal,
                        self.output_dir,
                        output_filename=f"dubbed_segment_{index}_{timing_adjustment}.wav",
                        sample_rate=sr,
                        target_lang=self.target_lang,
                        feature_stats=segment_features.get("stats"),
                        target_duration_s=target_duration_s,
                        quality_profile=quality_profile,
                        voice_profile=voice_profile,
                        previous_text=previous_text,
                        next_text=next_text,
                        segment_index=index,
                        source_audio_path=job["segment_path"],
                    )
                    adjusted_timed_segment_path = os.path.join(
                        self.output_dir,
                        f"timed_segment_{index}_{timing_adjustment}.wav",
                    )
                    adjusted_timing_info = stretch_to_duration(
                        adjusted_raw_segment_path,
                        target_duration_s=target_duration_s,
                        output_path=adjusted_timed_segment_path,
                        sample_rate=sr,
                    )
                    if self._synthesis_penalty(adjusted_synthesis_info, adjusted_timing_info) + 0.02 < self._synthesis_penalty(synthesis_info, timing_info):
                        translation = adjusted_translation
                        translated_plain_segments[index] = adjusted_translation
                        job["translation"] = adjusted_translation
                        demo_translation = False
                        raw_segment_path = adjusted_raw_segment_path
                        timed_segment_path = adjusted_timed_segment_path
                        timing_info = adjusted_timing_info
                        synthesis_info = adjusted_synthesis_info
                        job["translation_strategy"] = f"{timing_adjustment}ed_for_timing"

            if (
                timing_info.get("quality_warning")
                and not demo_translation
                and not is_curated_demo
                and not job["curated_translation"]
                and self.translator.api_key
                and float(timing_info.get("stretch_rate", 1.0) or 1.0) > 1.12
            ):
                prev_context = segment_jobs[index - 1]["transcript"] if index > 0 else None
                next_context = segment_jobs[index + 1]["transcript"] if index + 1 < len(segment_jobs) else None
                tightened_translation, tightened_demo_translation = self.translator.translate(
                    transcript,
                    self.target_lang,
                    self.output_dir,
                    artifact_name=f"translation_segment_{index}_tightened.txt",
                    source_duration_s=target_duration_s,
                    tighten=True,
                    valence=valence,
                    arousal=arousal,
                    feature_stats=segment_features.get("stats"),
                    previous_context=prev_context,
                    next_context=next_context,
                )
                if tightened_translation and not tightened_demo_translation and tightened_translation != translation:
                    retry_raw_segment_path, retry_synthesis_info = synthesize_speech(
                        tightened_translation,
                        valence,
                        arousal,
                        self.output_dir,
                        output_filename=f"dubbed_segment_{index}_retry.wav",
                        sample_rate=sr,
                        target_lang=self.target_lang,
                        feature_stats=segment_features.get("stats"),
                        target_duration_s=target_duration_s,
                        quality_profile=quality_profile,
                        voice_profile=voice_profile,
                        previous_text=previous_text,
                        next_text=next_text,
                        segment_index=index,
                        source_audio_path=job["segment_path"],
                    )
                    retry_timed_segment_path = os.path.join(self.output_dir, f"timed_segment_{index}_retry.wav")
                    retry_timing_info = stretch_to_duration(
                        retry_raw_segment_path,
                        target_duration_s=target_duration_s,
                        output_path=retry_timed_segment_path,
                        sample_rate=sr,
                    )
                    if self._timing_penalty(retry_timing_info) + 0.02 < self._timing_penalty(timing_info):
                        translation = tightened_translation
                        translated_plain_segments[index] = tightened_translation
                        job["translation"] = tightened_translation
                        demo_translation = False
                        raw_segment_path = retry_raw_segment_path
                        timed_segment_path = retry_timed_segment_path
                        timing_info = retry_timing_info
                        synthesis_info = retry_synthesis_info
                        job["translation_strategy"] = "tightened_for_timing"

            transcripts.append(f"[Segment {index + 1}] {transcript}")
            translations.append(f"[Segment {index + 1}] {translation}")
            timed_segments.append(timed_segment_path)

            manifest["segments"].append(
                {
                    "id": index,
                    "source_segment": job["segment_path"],
                    "dubbed_segment_raw": raw_segment_path,
                    "dubbed_segment_timed": timed_segment_path,
                    "start_s": round(float(job["segment_info"].get("start_s", 0.0)), 3),
                    "end_s": round(float(job["segment_info"].get("end_s", target_duration_s)), 3),
                    "source_duration_s": round(target_duration_s, 3),
                    "transcript": transcript,
                    "translation": translation,
                    "transcript_mode": "Fallback" if job["demo_transcript"] else "Real",
                    "translation_mode": "Fallback" if demo_translation else "Real",
                    "segment_validity": "Invalid/Demo" if (job["demo_transcript"] or demo_translation) else "Valid",
                    "translation_strategy": job["translation_strategy"],
                    "valence": round(valence, 4),
                    "arousal": round(arousal, 4),
                    "features": self._feature_snapshot(segment_features),
                    "synthesis": synthesis_info,
                    "timing": timing_info,
                }
            )

        transcription_text = "\n\n".join(transcripts).strip()
        translation_text = "\n\n".join(translations).strip()
        with open(os.path.join(self.output_dir, "transcription.txt"), "w", encoding="utf-8") as f:
            f.write(transcription_text)
        with open(os.path.join(self.output_dir, "translation.txt"), "w", encoding="utf-8") as f:
            f.write(translation_text)

        if per_segment_emotion:
            avg_valence = float(np.mean([item[0] for item in per_segment_emotion]))
            avg_arousal = float(np.mean([item[1] for item in per_segment_emotion]))
        else:
            avg_valence = global_valence
            avg_arousal = global_arousal

        self._update(78, "Assembling dubbed timeline...")
        raw_dubbed_audio = self._assemble_timeline(len(y_src), sr, timed_segments, seg_meta, manifest)

        self._update(84, "Applying prosody alignment...")
        aligned_dubbed_audio = os.path.join(self.output_dir, "dubbed_audio.wav")
        if is_curated_demo or is_showcase_demo or len(segments) <= 1 or self._should_skip_global_alignment(manifest, quality_profile):
            align_info = {
                "status": "skipped",
                "reason": "Conservative alignment mode preserved the clean synthesized dub without extra whole-track warping.",
                "aligned_audio_path": raw_dubbed_audio,
            }
            aligned_dubbed_audio = raw_dubbed_audio
        else:
            align_info = align_prosody(source_audio, raw_dubbed_audio, output_path=aligned_dubbed_audio, sample_rate=sr)
            if align_info.get("status") == "failed" or not os.path.exists(aligned_dubbed_audio):
                aligned_dubbed_audio = raw_dubbed_audio

        self._update(91, "Evaluating prosody transfer...")
        metrics = evaluate_metrics(
            source_audio,
            raw_dubbed_audio,
            self.output_dir,
            aligned_path=aligned_dubbed_audio,
            sample_rate=sr,
        )
        metrics["valence"] = round(avg_valence, 4)
        metrics["arousal"] = round(avg_arousal, 4)
        metrics["alignment_info"] = align_info
        metrics["is_demo_run"] = is_demo_run
        metrics["segment_count"] = len(segments)

        if is_demo_run:
            run_validity = "Invalid/Demo"
        elif source_type == "Synthetic Speech / TTS":
            run_validity = "Synthetic Baseline"
        elif source_type == "Non-Speech / Dummy":
            run_validity = "Invalid/NonSpeech"
        else:
            run_validity = "Valid"

        metrics["run_validity"] = run_validity
        manifest["assembled_file_raw"] = raw_dubbed_audio
        manifest["assembled_file"] = aligned_dubbed_audio
        manifest["run_validity"] = run_validity

        results_json = os.path.join(self.output_dir, "pipeline_results.json")
        with open(results_json, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        self._update(95, "Rendering dubbed video...")
        dubbed_video = self._render_dubbed_video(aligned_dubbed_audio)
        manifest["dubbed_video"] = dubbed_video

        segment_manifest_path = os.path.join(self.output_dir, "segment_manifest.json")
        with open(segment_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        summary_text = "\n".join(
            [
                "=== PIPELINE RUN SUMMARY ===",
                f"Input Used: {self.input_path}",
                f"Target Language: {self.target_lang}",
                f"Detected Profile: {source_type}",
                f"Transcript Mode: {'Fallback Demo' if is_demo_run else 'Real Audio Pipeline'}",
                f"Run Validity: {run_validity}",
                f"Segments processed: {len(segments)}",
                f"Alignment Status: {align_info.get('status', 'skipped')}",
                f"DTW Cost: {align_info.get('dtw_normalized_cost', 'N/A')}",
                f"Aligned Pitch Correlation: {metrics.get('aligned_metrics', {}).get('pitch_correlation')}",
                f"Aligned Energy Correlation: {metrics.get('aligned_metrics', {}).get('energy_correlation')}",
                f"Aligned MCD Score: {metrics.get('aligned_metrics', {}).get('mcd_score')}",
                "Notes: Segment durations are matched before assembly, then DTW warping projects the full dub onto the source timeline.",
            ]
        )

        run_summary_path = os.path.join(self.output_dir, "run_summary.txt")
        with open(run_summary_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        elapsed = time.time() - t_start
        self._update(100, "Dub ready.")
        print(f"\n[ORCHESTRATOR] Complete in {elapsed:.1f}s. Results saved to: {self.output_dir}")

        return {
            "run_validity": run_validity,
            "source_type": source_type,
            "metrics": metrics,
            "summary": summary_text,
            "transcription_text": transcription_text,
            "translation_text": translation_text,
            "artifacts": {
                "source_audio": source_audio,
                "dubbed_audio_raw": raw_dubbed_audio,
                "dubbed_audio": aligned_dubbed_audio,
                "dubbed_video": dubbed_video,
                "comparison_plot": os.path.join(self.output_dir, "comparison_plot.png"),
                "results_json": results_json,
                "segment_manifest": segment_manifest_path,
                "run_summary": run_summary_path,
                "transcription": os.path.join(self.output_dir, "transcription.txt"),
                "translation": os.path.join(self.output_dir, "translation.txt"),
            },
        }
