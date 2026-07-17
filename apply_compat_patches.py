"""
apply_compat_patches.py
=======================
Applies all compatibility patches needed to run pyannote.audio 3.4.0
with torchaudio >= 2.9, PyTorch >= 2.6, and huggingface_hub >= 0.20.

Run once after setting up the venv on any machine:
    python apply_compat_patches.py

Safe to re-run — checks if patches are already applied before modifying.
"""

import sys
import site
import importlib
from pathlib import Path


def find_site_packages():
    """Find the active venv's site-packages directory."""
    for p in sys.path:
        pp = Path(p)
        if pp.name == "site-packages" and pp.exists():
            return pp
    # fallback
    for p in site.getsitepackages():
        if Path(p).exists():
            return Path(p)
    return Path(site.getusersitepackages())


SP = find_site_packages()
print(f"Site-packages: {SP}\n")

ERRORS = []


def patch_file(rel_path: str, old: str, new: str, description: str):
    """Replace `old` with `new` in a file. Skips if already patched."""
    path = SP / rel_path
    if not path.exists():
        print(f"  [SKIP] File not found: {rel_path}")
        return

    content = path.read_text(encoding="utf-8")
    if old not in content:
        if new.strip() in content or "# COMPAT PATCH" in content:
            print(f"  [OK] Already patched: {rel_path}")
        else:
            print(f"  [SKIP] Marker not found: {rel_path}")
        return

    content = content.replace(old, new, 1)
    path.write_text(content, encoding="utf-8")
    print(f"  [PATCHED] {rel_path} -- {description}")


# ============================================================
# PATCH A: torchaudio/__init__.py
#   Add AudioMetaData, list_audio_backends, soundfile fallback
# ============================================================
print("=== Patch A: torchaudio/__init__.py ===")

TORCHAUDIO_SHIMS = '''
# ---------------------------------------------------------------------------
# COMPAT PATCH: Compatibility shims for pyannote.audio 3.x (removed in torchaudio 2.9+)
# ---------------------------------------------------------------------------

class AudioMetaData:
    """Backward-compatible replacement for torchaudio.AudioMetaData (removed in 2.9+)."""
    def __init__(self, sample_rate=0, num_frames=0, num_channels=0,
                 bits_per_sample=0, encoding="UNKNOWN"):
        self.sample_rate = sample_rate
        self.num_frames = num_frames
        self.num_channels = num_channels
        self.bits_per_sample = bits_per_sample
        self.encoding = encoding

    def __repr__(self):
        return (f"AudioMetaData(sample_rate={self.sample_rate}, num_frames={self.num_frames}, "
                f"num_channels={self.num_channels}, bits_per_sample={self.bits_per_sample}, "
                f"encoding={self.encoding!r})")


def list_audio_backends():
    """Backward-compatible replacement for torchaudio.list_audio_backends (removed in 2.9+)."""
    return ["soundfile"]


'''

patch_file(
    "torchaudio/__init__.py",
    old="def load(\n",
    new=TORCHAUDIO_SHIMS + "def load(\n",
    description="Added AudioMetaData class and list_audio_backends shim",
)

# Patch load() body to use soundfile fallback
LOAD_OLD = '''    return load_with_torchcodec(
        uri,
        frame_offset=frame_offset,
        num_frames=num_frames,
        normalize=normalize,
        channels_first=channels_first,
        format=format,
        buffer_size=buffer_size,
        backend=backend,
    )'''

LOAD_NEW = '''    # COMPAT PATCH: Try torchcodec first, fall back to soundfile if not installed
    try:
        return load_with_torchcodec(
            uri,
            frame_offset=frame_offset,
            num_frames=num_frames,
            normalize=normalize,
            channels_first=channels_first,
            format=format,
            buffer_size=buffer_size,
            backend=backend,
        )
    except ImportError:
        pass  # torchcodec not installed — fall back to soundfile

    import numpy as _np
    import soundfile as _sf

    start = frame_offset
    frames_to_read = -1 if num_frames == -1 else num_frames
    if hasattr(uri, "read"):
        data, sample_rate = _sf.read(uri, start=start, frames=frames_to_read,
                                     dtype="float32", always_2d=True)
    else:
        data, sample_rate = _sf.read(str(uri), start=start, frames=frames_to_read,
                                     dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T if channels_first else data)
    return waveform, sample_rate'''

patch_file(
    "torchaudio/__init__.py",
    old=LOAD_OLD,
    new=LOAD_NEW,
    description="soundfile fallback for torchaudio.load()",
)


# ============================================================
# PATCH B: pyannote/audio/core/io.py
#   Replace torchaudio.list_audio_backends() and torchaudio.info()
# ============================================================
print("\n=== Patch B: pyannote/audio/core/io.py ===")

IO_SHIMS_OLD = "import numpy as np\nimport torch.nn.functional as F\nimport torchaudio"
IO_SHIMS_NEW = '''import numpy as np
import soundfile as _sf
import torch.nn.functional as F
import torchaudio


# COMPAT PATCH: torchaudio.list_audio_backends and torchaudio.info removed in 2.9+
def _list_audio_backends():
    return ["soundfile"]


class _TorchaudioInfoCompat:
    def __init__(self, sf_info):
        self.num_frames = sf_info.frames
        self.sample_rate = sf_info.samplerate
        self.num_channels = sf_info.channels
        self.bits_per_sample = 16
        self.encoding = "PCM_S"


def _torchaudio_info(file, backend=None):
    sf_info = _sf.info(file)
    return _TorchaudioInfoCompat(sf_info)'''

patch_file(
    "pyannote/audio/core/io.py",
    old=IO_SHIMS_OLD,
    new=IO_SHIMS_NEW,
    description="Added _list_audio_backends, _TorchaudioInfoCompat, _torchaudio_info shims",
)

# Replace calls to torchaudio.list_audio_backends() in get_torchaudio_info
patch_file(
    "pyannote/audio/core/io.py",
    old='''    if not backend:
        backends = (
            torchaudio.list_audio_backends()
        )  # e.g ['ffmpeg', 'soundfile', 'sox']
        backend = "soundfile" if "soundfile" in backends else backends[0]

    info = torchaudio.info(file["audio"], backend=backend)''',
    new='''    if not backend:
        backends = _list_audio_backends()  # COMPAT PATCH
        backend = "soundfile" if "soundfile" in backends else backends[0]

    info = _torchaudio_info(file["audio"], backend=backend)  # COMPAT PATCH''',
    description="Replaced torchaudio.list_audio_backends() and torchaudio.info() in get_torchaudio_info",
)

# Replace calls in Audio.__init__
patch_file(
    "pyannote/audio/core/io.py",
    old='''        if not backend:
            backends = (
                torchaudio.list_audio_backends()
            )  # e.g ['ffmpeg', 'soundfile', 'sox']
            backend = "soundfile" if "soundfile" in backends else backends[0]''',
    new='''        if not backend:
            backends = _list_audio_backends()  # COMPAT PATCH
            backend = "soundfile" if "soundfile" in backends else backends[0]''',
    description="Replaced torchaudio.list_audio_backends() in Audio.__init__",
)


# ============================================================
# PATCH C: huggingface_hub/utils/_validators.py
#   Map use_auth_token → token automatically
# ============================================================
print("\n=== Patch C: huggingface_hub/utils/_validators.py ===")

VALIDATORS_OLD = "    return new_kwargs\n"
VALIDATORS_NEW = '''    # COMPAT PATCH: use_auth_token -> token (removed in huggingface_hub >= 0.20)
    use_auth_token = new_kwargs.pop("use_auth_token", None)
    if use_auth_token is not None:
        if new_kwargs.get("token") is None:
            new_kwargs["token"] = use_auth_token

    return new_kwargs
'''

patch_file(
    "huggingface_hub/utils/_validators.py",
    old=VALIDATORS_OLD,
    new=VALIDATORS_NEW,
    description="Auto-remaps use_auth_token -> token for all hf_hub_download calls",
)


# ============================================================
# PATCH D: lightning_fabric/utilities/cloud_io.py
#   Allow TorchVersion in safe globals + fallback weights_only=False
# ============================================================
print("\n=== Patch D: lightning_fabric/utilities/cloud_io.py ===")

CLOUD_IO_OLD = "log = logging.getLogger(__name__)\n"
CLOUD_IO_NEW = '''log = logging.getLogger(__name__)

# COMPAT PATCH: PyTorch 2.6+ defaults weights_only=True; pyannote checkpoints embed TorchVersion
try:
    import torch.torch_version
    import torch.serialization
    torch.serialization.add_safe_globals([torch.torch_version.TorchVersion])
except Exception:
    pass

'''

patch_file(
    "lightning_fabric/utilities/cloud_io.py",
    old=CLOUD_IO_OLD,
    new=CLOUD_IO_NEW,
    description="Allowlisted TorchVersion in torch safe globals",
)

CLOUD_LOAD_OLD = '''    fs = get_filesystem(path_or_url)
    with fs.open(path_or_url, "rb") as f:
        return torch.load(
            f,
            map_location=map_location,  # type: ignore[arg-type]
            weights_only=weights_only,
        )'''

CLOUD_LOAD_NEW = '''    fs = get_filesystem(path_or_url)
    with fs.open(path_or_url, "rb") as f:
        try:
            return torch.load(
                f,
                map_location=map_location,  # type: ignore[arg-type]
                weights_only=weights_only,
            )
        except Exception:
            # COMPAT PATCH: fallback for legacy pyannote checkpoints with non-tensor globals
            f.seek(0)
            return torch.load(
                f,
                map_location=map_location,  # type: ignore[arg-type]
                weights_only=False,
            )'''

patch_file(
    "lightning_fabric/utilities/cloud_io.py",
    old=CLOUD_LOAD_OLD,
    new=CLOUD_LOAD_NEW,
    description="Added weights_only=False fallback for legacy checkpoint loading",
)


# ============================================================
# Done
# ============================================================
print("")
print("[DONE] All patches applied. You can now run: python batch_process_audio.py")
print("")
print("Remember to set your HuggingFace token before running:")
print("  Windows cmd:   set HF_TOKEN=hf_yourTokenHere")
print("  PowerShell:    $env:HF_TOKEN='hf_yourTokenHere'")
print("  Linux/macOS:   export HF_TOKEN=hf_yourTokenHere")
