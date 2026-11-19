# -*- coding: utf-8 -*-
"""예시 문장으로 시험 실행:  python -m diary_pipeline        (일기 모드)
                            python -m diary_pipeline story  (동화 모드)"""
import sys

from . import run_diary, run_story, to_json

if len(sys.argv) > 1 and sys.argv[1] == "story":
    for text in ["아침에 엄마랑 김밥을 만들었다",          # 맞춤법이 맞음 → story(원문 + 새 표현 2개)
                 "집에 오니 강아지가 나를 반겼어요",
                 "동생이 금새 잠이 들었다"]:              # 맞춤법이 틀림 → 일기 모드와 같은 교정
        print(f"=== [동화] 입력: {text}")
        print(to_json(run_story({"user_input": text})), "\n")
    sys.exit()

for text in ["오늘 학교에서 친구랑 재미있게 놀았다", "우리는 할수있다", "몇일 뒤에 방을 깨끗히 치웠다",
             "저녁에 엄마랑 같이 설겆이를 했다",   # 표준어 사정 원칙(제20항) 근거를 찾는지 확인용
             "할머니 집은 옛스러운 느낌이 났다",   # 옛스럽다 → 예스럽다
             "선생님 내일 학교에서 뵈요",          # 뵈요 → 봬요 (되어→돼 와 같은 줄임)
             "동생이 금새 잠이 들었다",            # 금새 → 금세
             "나를 도와준 사람은 엄마 뿐이다",     # 엄마 뿐이다 → 엄마뿐이다 (낱말 뒤에 붙는 말은 붙여 씀)
             "ㅋㅋㅋ"]:
    print(f"=== 입력: {text}")
    print(to_json(run_diary({"user_input": text})), "\n")
