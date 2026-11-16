# -*- coding: utf-8 -*-
"""③ 쿼리 재작성 (형태소 분석 Kiwi, LLM 안 씀).   읽는 키: difference, original_sentence, revised_sentence → 쓰는 키: rewritten_queries, query_types
수정 1건마다 어절 diff(앞뒤 1어절) 질의를 만들고, Kiwi로 문법 특징을 뽑아 판정 유형(①~④)을 정한 뒤 특징을 질의 앞에 붙인다.
  예: "의존 명사 '수' 띄어쓰기 | 문제를 풀수 없었다 → 문제를 풀 수 없었다"
규칙은 RAG 평가 노트북과 같은 코드다. 규칙을 바꾸면 검색 성능이 달라지므로 평가 노트북으로 다시 확인한다."""
import difflib
import re
import unicodedata

CTX = 1                                     # 질의에 붙일 앞뒤 어절 수
PUNCT_RE = re.compile(r"[.,!?~…·;:\"'“”‘’()\[\]{}<>「」『』\-–—/]+")

_kiwi = {}


def get_kiwi():
    """Kiwi 형태소 분석기를 한 번만 불러온다."""
    if "k" not in _kiwi:
        from kiwipiepy import Kiwi
        _kiwi["k"] = Kiwi()
    return _kiwi["k"]


# ---------------------------------------------------------------------------
# 어절 단위 diff (평가 노트북 셀 2)
# ---------------------------------------------------------------------------
def _nfc(s):
    return unicodedata.normalize("NFC", str(s)).strip()


def _core(tokens):
    return PUNCT_RE.sub("", " ".join(tokens))


def _ns(s):
    return PUNCT_RE.sub("", _nfc(s)).replace(" ", "")


def word_diffs(src: str, cor: str, ctx: int = CTX) -> list[dict]:
    """원문·교정문을 어절 단위로 비교. 문장 부호만 바뀐 조각은 제외.
    항목: {err, cor, query, i1, i2}  (i1, i2 = 원문 어절 번호 범위)"""
    a, b = _nfc(src).split(), _nfc(cor).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        err_tok, cor_tok = a[i1:i2], b[j1:j2]
        if _core(err_tok) == _core(cor_tok):
            continue
        L, R = max(i1 - ctx, 0), min(i2 + ctx, len(a))
        Lb, Rb = max(j1 - ctx, 0), min(j2 + ctx, len(b))
        err_ctx = re.sub(r"[.!?~…]+$", "", " ".join(a[L:R]))
        cor_ctx = re.sub(r"[.!?~…]+$", "", " ".join(b[Lb:Rb]))
        out.append({"err": " ".join(err_tok), "cor": " ".join(cor_tok), "query": f"{err_ctx} → {cor_ctx}",
                    "i1": i1, "i2": i2})
    return out


def match_diff(src: str, segs: list[dict], start: int, end: int):
    """② extract_diff 의 바뀐 곳(원문 글자 위치 start~end)과 겹치는 어절 diff 조각. 없으면 None."""
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", src)]     # start/end 가 원문 기준 위치이므로 원문 그대로
    idx = [k for k, (s, e) in enumerate(words) if s < end and e > start]
    if not idx:
        return None
    w1, w2 = idx[0], idx[-1] + 1
    for d in segs:
        if (d["i1"] < w2 and d["i2"] > w1) or (d["i1"] == d["i2"] and w1 <= d["i1"] <= w2):
            return d
    return None


# ---------------------------------------------------------------------------
# 형태소 분석 판정 (평가 노트북 셀 8)
# ---------------------------------------------------------------------------
_UNIT = set("개 명 번 살 년 월 일 시 분 초 시간 달 주 개월 배 권 장 대 마리 잔 병 가지 군데 층 학년 차 회 벌 채 켤레 강 판 그루 송이 척 쪽 원 킬로 미터 센티".split())
_NUM_MM = set("한 두 세 네 다섯 여섯 일곱 여덟 아홉 열 몇 스무 서 너 여러 수십 수백 첫".split())
_LIST = set("겸 내지 대 등 및 등등 등속 등지".split())
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def _bounds(s):
    s = PUNCT_RE.sub("", _nfc(s)); b, k = set(), 0
    for ch in s:
        if ch == " ": b.add(k)
        else: k += 1
    return b


def _toks(s):
    s = PUNCT_RE.sub("", _nfc(s)); m, k = [], 0
    for ch in s:
        m.append(k)
        if ch != " ": k += 1
    m.append(k)
    return [(m[t.start], t.form, t.tag) for t in get_kiwi().tokenize(s)]


def _jong(ch):
    o = ord(ch) - 0xAC00
    return _JONG[o % 28] if 0 <= o < 11172 else ""


def _shift_typo(x, y):
    """한 글자에서 Shift 키 차이(ㅂ/ㅃ, ㅐ/ㅒ 등)만 다른 입력 오타인지"""
    if len(x) != 1 or len(y) != 1: return False
    ox, oy = ord(x) - 0xAC00, ord(y) - 0xAC00
    if not (0 <= ox < 11172 and 0 <= oy < 11172): return False
    ax, ay = (ox // 588, (ox % 588) // 28, ox % 28), (oy // 588, (oy % 588) // 28, oy % 28)
    d = [i for i in range(3) if ax[i] != ay[i]]
    if len(d) != 1: return False
    i = d[0]; p = tuple(sorted((ax[i], ay[i])))
    return ((i == 0 and p in {(9, 10), (3, 4), (7, 8), (0, 1), (12, 13)}) or
            (i == 2 and p in {(19, 20), (1, 2)}) or (i == 1 and p in {(1, 3), (5, 7)}))


def gram_features(err: str, cor: str):
    """반환: (띄어쓰기 특징 목록, 표기 특징 목록)"""
    kiwi = get_kiwi()
    sp_f, lt_f = [], []
    e, c = _ns(err), _ns(cor)
    sm = difflib.SequenceMatcher(None, e, c, autojunk=False)
    c2e = {b + t: a + t for a, b, size in sm.get_matching_blocks() for t in range(size)}
    be, bc = _bounds(err), _bounds(cor)
    T = _toks(cor); start = {}
    for i, t in enumerate(T): start.setdefault(t[0], i)
    for k in sorted(bc):                                    # 새로 띄운 경계
        if k in c2e and c2e[k] in be: continue
        i = start.get(k)
        if i is None: continue
        _, f, tg = T[i]; p = T[i-1] if i > 0 else None
        if f in _LIST: sp_f.append(f"열거하는 말 '{f}' 띄어쓰기")
        elif (tg == "NNB" or f in _UNIT) and p and (p[2] in ("SN", "NR") or p[1] in _NUM_MM):
            sp_f.append(f"수 뒤 단위 명사 '{f}' 띄어쓰기")
        elif tg == "NNB" or f in ("거", "걸", "건", "게"): sp_f.append(f"의존 명사 '{f}' 띄어쓰기")
        elif tg == "VX": sp_f.append(f"보조 용언 '{f}' 띄어쓰기")
        elif tg.startswith("J"): sp_f.append(f"조사 '{f}' 앞 띄어쓰기")
        elif tg.startswith("XS"): sp_f.append(f"접미사 '{f}' 앞 띄어쓰기")
        else: sp_f.append(f"단어 '{f}' 앞 띄어쓰기")
    inv = {v: k for k, v in c2e.items()}
    for j in sorted(be):                                    # 붙인 경계
        k = inv.get(j)
        if k is None or k in bc: continue
        i = start.get(k)
        if i is None: continue
        _, f, tg = T[i]
        if tg.startswith("J") or tg == "VCP": sp_f.append(f"조사 '{f}' 붙여 쓰기")
        elif tg.startswith("XS") or tg.startswith("E"): sp_f.append(f"접미사·어미 '{f}' 붙여 쓰기")
        elif tg == "VX": sp_f.append(f"보조 용언 '{f}' 붙여 쓰기")
        else: sp_f.append(f"'{f}' 앞 붙여 쓰기(한 단어)")
    for op, a1, a2, b1, b2 in sm.get_opcodes():             # 글자 표기 변화
        if op == "equal": continue
        x, y = e[a1:a2], c[b1:b2]
        # 주의: #13 평가 때의 순서 그대로다. '갈께→갈게'처럼 'ㄲ→ㄱ'은 아래 입력 오타 검사에 먼저 걸려
        #       '-ㄹ게 예사소리' 특징이 붙지 않는다(평가 584문항 중 9문항). 순서를 바꾸면 평가 노트북으로 다시 확인할 것
        if _shift_typo(x, y):
            lt_f.append(f"'{x}'를 '{y}'로 고친 표기(입력 오타)"); continue
        wy = c[max(b1-2, 0):b2+2]
        if ("돼" in x + y or "됬" in x or "됀" in x): lt_f.append("'되'와 '돼' 구별, '되어'가 줄어든 '돼' 표기")
        elif "않" in y or ("안" in y and "않" in x): lt_f.append("'않다'(아니하다)와 부사 '안' 구별 표기")
        elif "잖" in y or "찮" in y: lt_f.append("'-지 않-'이 줄어든 '-잖-', '-하지 않-'이 줄어든 '-찮-' 표기")
        elif any(s in x for s in ("께", "껄", "쑤록", "찌")) and any(s in y for s in ("게", "걸", "수록", "지")):
            lt_f.append(f"어미 '{y}' 예사소리 표기(-ㄹ게, -ㄹ걸, -ㄹ수록, -ㄹ지)")
        elif x == "가" and y == "까" and b1 > 0 and _jong(c[b1-1]) == "ㄹ" and c[b2:b2+1] != "지":
            lt_f.append("의문 어미 '-ㄹ까' 된소리 표기")
        elif ("히" in y and "이" in x) or ("이" in y and "히" in x): lt_f.append(f"부사 끝 '-이'와 '-히' 구별 표기('{wy}')")
        elif ("더" in y and "드" in x) or ("던" in y and "든" in x) or ("든" in y and "던" in x):
            lt_f.append("지난 일 '-더라, -던'과 선택 '-든' 구별 표기")
        elif "로서" in wy or "로써" in wy: lt_f.append("'로서'와 '로써' 구별 표기")
        elif "의" in y and "이" in x: lt_f.append(f"'ㅢ' 표기('{wy}')")
        elif "며칠" in wy: lt_f.append("'며칠' 표기")
        else:
            stem = next((t for t in kiwi.tokenize(c[max(b1-3, 0):b2+3]) if t.tag in ("VV", "VA", "VX")), None)
            lt_f.append(f"용언 '{stem.form}다'의 어간과 어미를 밝혀 적은 표기('{wy}')" if stem else f"'{x}'를 '{y}'로 고친 표기")
    return list(dict.fromkeys(sp_f)), list(dict.fromkeys(lt_f))


SPACE_SPECIFIC = ("의존 명사", "수 뒤 단위 명사", "보조 용언", "조사 '", "열거하는 말")   # 제5장 구체 규칙

TYPE_SPELLING = "①표기만"
TYPE_SPACE_SPECIFIC = "②띄어쓰기+구체"
TYPE_SPACE_MIXED = "③띄어쓰기+표기"
TYPE_SPACE_GENERAL = "④일반 띄어쓰기"


def decide(sp_f: list, lt_f: list) -> str:
    """판정 유형: ①표기만 ②띄어쓰기+구체 ③띄어쓰기+표기 ④일반 띄어쓰기"""
    if not sp_f:
        return TYPE_SPELLING
    if any(k in f for f in sp_f for k in SPACE_SPECIFIC):
        return TYPE_SPACE_SPECIFIC
    if lt_f:
        return TYPE_SPACE_MIXED
    return TYPE_SPACE_GENERAL


def enrich_query(sp_f: list, lt_f: list, query: str) -> str:
    """형태소 질의 보강: 특징(최대 4개, 입력 오타 제외) + 원래 diff 질의"""
    feats = [f for f in (sp_f + lt_f) if "입력 오타" not in f][:4]
    return ("; ".join(feats) + " | " if (sp_f or lt_f) else "") + query     # 평가 노트북과 같은 조건


# ---- 노드 ----
def rewrite_queries(state: dict) -> dict:
    src, cor = state["original_sentence"], state["revised_sentence"]
    segs = word_diffs(src, cor)                              # 평가와 같은 어절 단위 diff
    queries, types = [], []
    for d in state["difference"]:
        seg = match_diff(src, segs, d["start"], d["end"])
        if seg is None:                                         # 어절 diff와 겹치는 조각이 없으면 ②의 표현 그대로
            seg = {"err": d["before"], "cor": d["after"], "query": f"{d['before']} → {d['after']}"}
        sp_f, lt_f = gram_features(seg["err"], seg["cor"])
        types.append(decide(sp_f, lt_f))
        queries.append(enrich_query(sp_f, lt_f, seg["query"]))
    return {"rewritten_queries": queries, "query_types": types}


def preload():
    get_kiwi()
