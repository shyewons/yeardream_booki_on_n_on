# -*- coding: utf-8 -*-
"""예시 문장으로 시험 실행:  python -m diary_pipeline"""
from . import run_diary, to_json

for text in ["오늘 학교에서 친구랑 재미있게 놀았다", "우리는 할수있다", "몇일 뒤에 방을 깨끗히 치웠다", "ㅋㅋㅋ"]:
    print(f"=== 입력: {text}")
    print(to_json(run_diary({"user_input": text})), "\n")
