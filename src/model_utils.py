"""Shared sequence encodings and small Torch helpers for benchmark baselines."""
from __future__ import annotations

import numpy as np


BASE_TO_CHANNEL = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3}


def onehot_flat(seqs, length: int = 30) -> np.ndarray:
    """Return position-major one-hot features with shape ``(N, length * 4)``."""
    x = np.zeros((len(seqs), length, 4), dtype=np.float32)
    for i, seq in enumerate(seqs):
        for j, base in enumerate(str(seq).upper()[:length]):
            channel = BASE_TO_CHANNEL.get(base)
            if channel is not None:
                x[i, j, channel] = 1.0
    return x.reshape(len(x), length * 4)


def onehot_channels(seqs, length: int = 30) -> np.ndarray:
    """Return Conv1d input with nucleotide channels: ``(N, 4, length)``."""
    flat = onehot_flat(seqs, length=length)
    return flat.reshape(len(flat), length, 4).transpose(0, 2, 1).copy()


def torch_device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def seed_everything(seed: int) -> None:
    import torch

    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
