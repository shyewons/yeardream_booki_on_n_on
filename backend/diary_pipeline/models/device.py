# -*- coding: utf-8 -*-
"""GPU/CPU 선택. torch 는 실제로 모델을 쓸 때 처음 불러온다."""
_cache = {}


def get_torch():
    if "torch" not in _cache:
        import torch
        _cache["torch"] = torch
        _cache["device"] = "cuda" if torch.cuda.is_available() else "cpu"
    return _cache["torch"]


def get_device() -> str:
    get_torch()
    return _cache["device"]
