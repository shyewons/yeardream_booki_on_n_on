# -*- coding: utf-8 -*-
"""칭찬 노드 (고칠 곳이 없을 때, 고정 문구).   읽는 키: 없음  →  쓰는 키: compliment
문구는 config.COMPLIMENT 에서 바꾼다."""
from .. import config


def compliment(state: dict) -> dict:
    return {"compliment": config.COMPLIMENT}
