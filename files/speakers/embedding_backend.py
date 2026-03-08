"""SpeechBrain ECAPA embedding extraction."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
from pathlib import Path
from typing import Callable, Iterator

import numpy as np
import requests
import torch


class SpeechBrainEmbeddingBackend:
    REPO_ID = "speechbrain/spkrec-ecapa-voxceleb"
    REQUIRED_FILES = (
        "hyperparams.yaml",
        "embedding_model.ckpt",
        "mean_var_norm_emb.ckpt",
        "classifier.ckpt",
        "label_encoder.txt",
        "config.json",
    )

    def __init__(self, models_root: Path) -> None:
        self.models_root = models_root / "speechbrain"
        self.models_root.mkdir(parents=True, exist_ok=True)
        self._classifier = None

    @property
    def asset_dir(self) -> Path:
        return self.models_root / "spkrec-ecapa-voxceleb"

    @property
    def marker_path(self) -> Path:
        return self.models_root / "asset-ready.json"

    @contextlib.contextmanager
    def _suppress_library_console_output(self) -> Iterator[None]:
        # `start.pyw` runs without a real console on Windows. SpeechBrain and
        # Hugging Face can try to open tqdm progress bars against stdout/stderr
        # while downloading the ECAPA asset. Redirecting both streams here keeps
        # those libraries from crashing under `pythonw`.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield

    def asset_ready(self) -> bool:
        if not self.asset_dir.exists():
            return False
        if not self.marker_path.exists():
            return False
        return all((self.asset_dir / filename).exists() for filename in self.REQUIRED_FILES)

    def _download_asset_files(self, progress_callback: Callable[[str], None] | None = None) -> Path:
        from huggingface_hub import HfApi, hf_hub_url

        self.asset_dir.mkdir(parents=True, exist_ok=True)
        model_info = HfApi().model_info(self.REPO_ID, files_metadata=True)
        wanted = {
            str(getattr(sibling, "rfilename", "")): int(getattr(sibling, "size", 0) or 0)
            for sibling in model_info.siblings
            if str(getattr(sibling, "rfilename", "")) in self.REQUIRED_FILES
        }
        missing = [filename for filename in self.REQUIRED_FILES if filename not in wanted]
        if missing:
            raise RuntimeError(f"SpeechBrain ECAPA asset is missing expected files: {', '.join(missing)}")

        total_bytes = sum(max(size, 0) for size in wanted.values())
        downloaded_total = 0
        last_reported_percent = -1

        for filename in self.REQUIRED_FILES:
            expected_size = wanted[filename]
            target_path = self.asset_dir / filename
            if target_path.exists() and (expected_size <= 0 or target_path.stat().st_size == expected_size):
                downloaded_total += max(expected_size, target_path.stat().st_size)
                continue
            part_path = target_path.with_suffix(target_path.suffix + ".part")
            part_path.unlink(missing_ok=True)
            file_url = hf_hub_url(self.REPO_ID, filename, revision=model_info.sha)
            if progress_callback is not None:
                progress_callback(f"Downloading SpeechBrain file {filename}...")
            with requests.get(file_url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with part_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded_total += len(chunk)
                        if total_bytes <= 0:
                            continue
                        percent = int(downloaded_total / total_bytes * 100)
                        if percent <= last_reported_percent and downloaded_total < total_bytes:
                            continue
                        last_reported_percent = percent
                        if progress_callback is not None:
                            downloaded_mb = downloaded_total / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            progress_callback(
                                f"SpeechBrain ECAPA: {percent:.0f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB) | {filename}"
                            )
            part_path.replace(target_path)

        return self.asset_dir

    def _reset_local_asset(self) -> None:
        self._classifier = None
        if self.asset_dir.exists():
            shutil.rmtree(self.asset_dir, ignore_errors=True)
        self.marker_path.unlink(missing_ok=True)

    def _load_classifier_from_local_asset(self):  # type: ignore[no-untyped-def]
        if self._classifier is None:
            os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
            from speechbrain.inference import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy
            try:
                from huggingface_hub.utils import disable_progress_bars
            except Exception:  # pragma: no cover - older hub versions
                disable_progress_bars = None

            if disable_progress_bars is not None:
                disable_progress_bars()

            with self._suppress_library_console_output():
                self._classifier = EncoderClassifier.from_hparams(
                    source=str(self.asset_dir),
                    savedir=str(self.asset_dir),
                    run_opts={"device": "cpu"},
                    local_strategy=LocalStrategy.NO_LINK,
                )
        return self._classifier

    def prepare_model(self, progress_callback: Callable[[str], None] | None = None, force_refresh: bool = False) -> Path:
        if force_refresh:
            if progress_callback is not None:
                progress_callback("Resetting the local SpeechBrain ECAPA asset before retrying.")
            self._reset_local_asset()
        if not self.asset_ready():
            if progress_callback is not None:
                progress_callback("Preparing the local SpeechBrain ECAPA asset for speaker grouping...")
            self._download_asset_files(progress_callback)
        if progress_callback is not None:
            progress_callback("Validating the local SpeechBrain ECAPA asset...")
        self._classifier = None
        self._load_classifier_from_local_asset()
        self.marker_path.write_text(
            json.dumps({"prepared": True, "asset_dir": str(self.asset_dir)}, indent=2),
            encoding="utf-8",
        )
        return self.marker_path

    def available(self) -> bool:
        return importlib.util.find_spec("speechbrain") is not None

    def ensure_ready(self, progress_callback: Callable[[str], None] | None = None, max_attempts: int = 2) -> None:
        if self._classifier is not None and self.asset_ready():
            return
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                self.prepare_model(progress_callback, force_refresh=attempt > 1)
                return
            except Exception as exc:
                last_error = exc
                if progress_callback is not None and attempt < max_attempts:
                    progress_callback(
                        f"SpeechBrain ECAPA preparation failed on attempt {attempt}/{max_attempts}. Retrying with a clean local asset..."
                    )
        if last_error is not None:
            raise last_error

    def extract_embedding(self, samples: np.ndarray, progress_callback: Callable[[str], None] | None = None) -> np.ndarray:
        self.ensure_ready(progress_callback)
        classifier = self._load_classifier_from_local_asset()
        tensor = torch.tensor(samples, dtype=torch.float32).unsqueeze(0)
        embedding = classifier.encode_batch(tensor)
        return embedding.squeeze().detach().cpu().numpy()
