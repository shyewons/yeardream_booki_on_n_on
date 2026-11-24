"""
교정 모델 비교 평가 스크립트

세 모델에 평가셋 100문장을 넣고 4개 지표를 계산한다.
※ 평가셋(data/)은 실제 아동 글이 아닌 합성 데이터다.
  1. 문장 정확도   : 100문장 중 정답 교정문과 완전히 같은 문장 비율
  2. 정밀도        : 모델이 한 수정 중 맞은 수정의 비율
  3. F0.5          : 정밀도를 재현율보다 2배 중시한 종합 점수 (재현율도 함께 출력)
  4. 과교정 비율   : 오류 없는 문장 20개 중 모델이 바꿔 버린 비율

사용법
  pip install -r requirements.txt
  python eval_correction.py --data data/synthetic_spelling_eval_100.jsonl --trust-remote-code

  # 모델 하나만:            --models et5
  # 이미 뽑은 출력으로 채점만: --score-only results/outputs.csv

출력 (results/ 폴더)
  outputs.csv        : 문장별 세 모델 출력, 응답 시간, 정답 여부, 맞게 고침/잘못 고침/놓침 수
  summary.csv        : 모델별 4개 지표 + 재현율 + 평균 응답 시간
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import statistics
import time

# ─────────────────────────────────────────────
# 모델 설정
# ─────────────────────────────────────────────
MODELS = {
    "et5": {
        "name": "① et5-typos-corrector",
        "repo": "j5ng/et5-typos-corrector",
        "kind": "t5",
        "prefix": "맞춤법을 고쳐주세요: ",       # 모델 카드 사용 예시와 동일
        "gen": {"max_length": 128, "num_beams": 5, "early_stopping": True},
    },
    "kogrammar": {
        "name": "② kogrammar-base",
        "repo": "theSOL1/kogrammar-base",
        "kind": "seq2seq",
        "prefix": "",
        "gen": {"max_length": 128, "num_beams": 4, "early_stopping": True},
    },
    "kanana": {
        "name": "③ Kanana-2-3B-instruct",
        # https://huggingface.co/kakaocorp/kanana-2-3b-instruct (--kanana-repo 로 바꿀 수 있음)
        "repo": "kakaocorp/kanana-2-3b-instruct",
        "kind": "causal",
        "gen": {"max_new_tokens": 128, "do_sample": False},   # 같은 입력이면 항상 같은 출력
    },
}

KANANA_SYSTEM = (
    "너는 초등학생이 쓴 한국어 문장의 맞춤법과 띄어쓰기를 고치는 교정기다. "
    "맞춤법과 띄어쓰기가 틀린 부분만 고치고, 단어 선택이나 말투, 문장부호는 바꾸지 않는다. "
    "틀린 곳이 없으면 문장을 그대로 출력한다. "
    "설명 없이 고친 문장 한 줄만 출력한다."
)


# ─────────────────────────────────────────────
# 모델 실행기
# ─────────────────────────────────────────────
class Runner:
    def __init__(self, key: str, device: str, repo_override: str | None = None,
                 trust_remote_code: bool = False):
        import torch
        from transformers import (AutoModelForCausalLM, AutoModelForSeq2SeqLM,
                                  AutoTokenizer, T5ForConditionalGeneration, T5Tokenizer)
        self.cfg = MODELS[key]
        self.torch = torch
        repo = repo_override or self.cfg["repo"]
        self.device = device
        dtype = torch.float16 if device == "cuda" else torch.float32
        kind = self.cfg["kind"]
        if kind == "t5":
            self.tok = T5Tokenizer.from_pretrained(repo)
            self.model = T5ForConditionalGeneration.from_pretrained(repo)
        elif kind == "seq2seq":
            self.tok = AutoTokenizer.from_pretrained(repo)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(repo)
        else:
            # 저장소에 들어 있는 모델 코드 실행 허용 여부 (--trust-remote-code)
            self.tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=trust_remote_code)
            self.model = AutoModelForCausalLM.from_pretrained(
                repo, torch_dtype=dtype, trust_remote_code=trust_remote_code)
        self.model.to(device).eval()

    def correct(self, text: str) -> str:
        torch = self.torch
        kind = self.cfg["kind"]
        with torch.no_grad():
            if kind in ("t5", "seq2seq"):
                enc = self.tok(self.cfg["prefix"] + text, return_tensors="pt").to(self.device)
                enc.pop("token_type_ids", None)
                out = self.model.generate(**enc, **self.cfg["gen"])
                return self.tok.decode(out[0], skip_special_tokens=True).strip()
            msgs = [{"role": "system", "content": KANANA_SYSTEM},
                    {"role": "user", "content": text}]
            # transformers 버전에 상관없이 input_ids / attention_mask 사전으로 받는다
            enc = self.tok.apply_chat_template(msgs, add_generation_prompt=True,
                                               return_tensors="pt", return_dict=True)
            enc = {k: v.to(self.device) for k, v in enc.items()
                   if k in ("input_ids", "attention_mask")}
            pad_id = self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id
            out = self.model.generate(**enc, pad_token_id=pad_id, **self.cfg["gen"])
            ans = self.tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
            return clean_llm_output(ans)


def clean_llm_output(ans: str) -> str:
    """범용 모델이 붙이는 군더더기 제거: 첫 줄만, 앞머리 표시와 감싼 따옴표 제거"""
    line = next((l for l in ans.strip().splitlines() if l.strip()), "")
    line = re.sub(r"^(교정\s*(결과|문장)?|수정\s*문장|정답|출력)\s*[:：]\s*", "", line.strip())
    if len(line) >= 2 and line[0] in "\"'“‘" and line[-1] in "\"'”’":
        line = line[1:-1]
    return line.strip()


# ─────────────────────────────────────────────
# 정규화 · 수정 추출 · 채점
# ─────────────────────────────────────────────
END_PUNCT = ".?!"


def normalize(pred: str, src: str) -> str:
    """공정 비교용: 공백 정리 + 원문 끝 문장부호가 출력에서 빠졌으면 되살림
    (① 모델은 학습할 때 쉼표·마침표를 지웠기 때문)"""
    pred = re.sub(r"\s+", " ", pred).strip()
    if src and src[-1] in END_PUNCT and (not pred or pred[-1] not in END_PUNCT):
        pred += src[-1]
    return pred


def extract_edits(src: str, tgt: str) -> set[tuple[int, int, str]]:
    """원문과 결과를 어절(띄어쓰기) 단위로 맞춰 보고 바뀐 부분을 수정 1건으로 본다.
    (원문 시작 위치, 원문 끝 위치, 바뀐 결과) 로 표현 → 정답 수정과 그대로 비교 가능.
    띄어쓰기 수정('할수'→'할 수')도 어절이 바뀌므로 수정 1건으로 잡힌다."""
    a, b = src.split(), tgt.split()
    edits = set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op != "equal":
            edits.add((i1, i2, " ".join(b[j1:j2])))
    return edits


def score_model(items: list[dict], preds: list[str]) -> dict:
    tp = fp = fn = 0
    exact = 0
    clean_total = clean_changed = 0
    per_item = []
    for it, pred in zip(items, preds):
        src, gold = it["입력문장"], it["정답교정문"]
        g, s = extract_edits(src, gold), extract_edits(src, pred)
        t, f, n = len(g & s), len(s - g), len(g - s)
        tp, fp, fn = tp + t, fp + f, fn + n
        ok = pred == gold
        exact += ok
        if it["유형"] == "오류 없음":
            clean_total += 1
            clean_changed += pred != src
        per_item.append({"정답여부": int(ok), "맞게고침": t, "잘못고침": f, "놓침": n})
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    F = 1.25 * P * R / (0.25 * P + R) if P + R else 0.0
    return {
        "문장 정확도": exact / len(items),
        "정밀도": P,
        "재현율": R,
        "F0.5": F,
        "과교정 비율": clean_changed / clean_total if clean_total else 0.0,
        "맞게 고침(TP)": tp, "잘못 고침(FP)": fp, "놓침(FN)": fn,
        "완벽히 고친 문장 수": exact, "전체 문장 수": len(items),
        "_per_item": per_item,
    }


# ─────────────────────────────────────────────
# 입출력
# ─────────────────────────────────────────────
def load_items(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def write_outputs(path, items, outs, times, scores):
    keys = list(outs)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        head = ["id", "유형", "입력문장", "정답교정문"]
        for k in keys:
            head += [f"{k}_출력", f"{k}_초", f"{k}_정답여부", f"{k}_맞게고침", f"{k}_잘못고침", f"{k}_놓침"]
        w.writerow(head)
        for i, it in enumerate(items):
            row = [it["id"], it["유형"], it["입력문장"], it["정답교정문"]]
            for k in keys:
                p = scores[k]["_per_item"][i]
                t = times[k][i] if times.get(k) else ""
                row += [outs[k][i], f"{t:.3f}" if t != "" else "", p["정답여부"], p["맞게고침"], p["잘못고침"], p["놓침"]]
            w.writerow(row)


def write_summary(path, scores, times):
    cols = ["문장 정확도", "정밀도", "F0.5", "과교정 비율", "재현율",
            "완벽히 고친 문장 수", "맞게 고침(TP)", "잘못 고침(FP)", "놓침(FN)"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["모델"] + cols + ["평균 응답 시간(초)", "p95 응답 시간(초)"])
        for k, sc in scores.items():
            ts = times.get(k) or []
            avg = f"{statistics.mean(ts):.3f}" if ts else ""
            p95 = f"{sorted(ts)[int(len(ts) * 0.95) - 1]:.3f}" if ts else ""
            w.writerow([MODELS[k]["name"]] + [round(sc[c], 4) if isinstance(sc[c], float) else sc[c]
                                               for c in cols] + [avg, p95])


def print_summary(scores, times):
    print("\n" + "=" * 78)
    print(f"{'모델':<28}{'문장정확도':>9}{'정밀도':>8}{'F0.5':>8}{'과교정':>8}{'재현율':>8}{'평균초':>8}")
    print("-" * 78)
    for k, sc in scores.items():
        ts = times.get(k) or []
        avg = f"{statistics.mean(ts):.2f}" if ts else "-"
        print(f"{MODELS[k]['name']:<28}{sc['문장 정확도']:>9.1%}{sc['정밀도']:>8.1%}{sc['F0.5']:>8.1%}"
              f"{sc['과교정 비율']:>8.1%}{sc['재현율']:>8.1%}{avg:>8}")
    print("=" * 78)
    print("문장 정확도는 100문장 기준, 과교정 비율은 오류 없는 20문장 기준입니다.")


def read_outputs_csv(path, keys):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    outs = {k: [r[f"{k}_출력"] for r in rows] for k in keys if f"{k}_출력" in rows[0]}
    times = {k: [float(r[f"{k}_초"]) for r in rows] for k in outs if rows[0].get(f"{k}_초")}
    return outs, times


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/synthetic_spelling_eval_100.jsonl")
    ap.add_argument("--models", default="et5,kogrammar,kanana")
    ap.add_argument("--kanana-repo", default=None, help="Kanana 저장소 이름 지정")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--out", default="results")
    ap.add_argument("--score-only", default=None, help="이미 뽑은 outputs.csv로 채점만")
    ap.add_argument("--no-punct-fix", action="store_true", help="끝 문장부호 보정 끄기")
    ap.add_argument("--trust-remote-code", action="store_true",
                    help="Kanana 저장소에 들어 있는 모델 코드 실행을 묻지 않고 허용")
    ap.add_argument("--rerun", action="store_true",
                    help="저장된 모델 결과(raw_*.json)가 있어도 다시 실행")
    args = ap.parse_args()

    items = load_items(args.data)
    keys = [k.strip() for k in args.models.split(",") if k.strip()]
    os.makedirs(args.out, exist_ok=True)

    if args.score_only:
        outs, times = read_outputs_csv(args.score_only, keys)
    else:
        import torch
        device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
        print(f"장치: {device}")
        outs, times = {}, {}
        for k in keys:
            # 이미 끝난 모델은 저장된 결과를 불러오고 건너뛴다 (다시 돌리려면 --rerun)
            raw_path = os.path.join(args.out, f"raw_{k}.json")
            if os.path.exists(raw_path) and not args.rerun:
                with open(raw_path, encoding="utf-8") as f:
                    saved = json.load(f)
                if len(saved["outputs"]) == len(items):
                    outs[k], times[k] = saved["outputs"], saved["times"]
                    print(f"\n[{MODELS[k]['name']}] 저장된 결과 사용 ({raw_path})")
                    continue
            print(f"\n[{MODELS[k]['name']}] 모델 불러오는 중...")
            runner = Runner(k, device, args.kanana_repo if k == "kanana" else None,
                            trust_remote_code=args.trust_remote_code and k == "kanana")
            runner.correct(items[0]["입력문장"])          # 첫 호출 준비 시간은 측정에서 제외
            outs[k], times[k] = [], []
            for i, it in enumerate(items, 1):
                t0 = time.perf_counter()
                pred = runner.correct(it["입력문장"])
                times[k].append(time.perf_counter() - t0)
                outs[k].append(pred)
                if i % 20 == 0:
                    print(f"  {i}/{len(items)}")
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump({"outputs": outs[k], "times": times[k]}, f, ensure_ascii=False)
            del runner
            if device == "cuda":
                torch.cuda.empty_cache()

    if not args.no_punct_fix:
        outs = {k: [normalize(p, it["입력문장"]) for p, it in zip(v, items)] for k, v in outs.items()}

    scores = {k: score_model(items, outs[k]) for k in outs}
    write_outputs(os.path.join(args.out, "outputs.csv"), items, outs, times, scores)
    write_summary(os.path.join(args.out, "summary.csv"), scores, times)
    print_summary(scores, times)
    print(f"\n결과 파일: {args.out}/outputs.csv, {args.out}/summary.csv")


if __name__ == "__main__":
    main()
