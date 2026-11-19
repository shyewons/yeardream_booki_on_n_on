// 글쓰기 화면의 두뇌. 화면(WritePage.jsx)은 여기의 상태를 그리기만 하고, 버튼을 누르면 여기의 함수를 부른다.
// frontend/temp/index.html 에 있던 동작을 그대로 옮겼다.
//
//   한 문장의 흐름:  submit() → /validate → (통과) /correct 스트림 → 문장 저장 → (동화) 표현 추천
//   저장은 한 번에 하나씩 차례로 한다 (saveChain). 문장 순서가 뒤바뀌지 않게 하기 위해서다.
//   문장의 저장 번호(seq)는 따로 갖지 않는다. 목록에서의 위치 + 1 이 그 번호다.
//
//   쓰던 문장 임시저장: 아직 통과하지 않은 입력칸의 글자를 서버(글의 draft 칸)에 덮어써 둔다 (syncDraft).
//     · 입력을 멈추고 DRAFT_DELAY_MS 가 지나면   · 쉬지 않고 치는 중이어도 DRAFT_MAX_WAIT_MS 마다
//     · '확인하기'를 누르면 바로   · 이 화면에서 나갈 때   · 화면이 가려질 때(앱 전환 · 화면 꺼짐, flushDraft)
//     칸이 하나라 매번 덮어쓴다 (문장 표에는 아무 줄도 생기지 않는다). 저장 여부는 st.draft 로 화면에 보여 준다.
//     다시 들어오면 boot() 가 입력칸에 되살린다 (다시쓰기 · 위에 넣기 중이었다면 그 상태까지).
//     문장이 저장되면 서버가 임시저장을 비운다.
//
//   문장 지우기: 줄마다 '지우기' → 화면 안에서 한 번 더 묻고 → 서버에서 뺀다 → UNDO_SECONDS 동안 '되돌리기'.
//     서버는 지운 줄을 DB 에서 지우지 않고 '빠진 줄'로 남긴다 (통계 · 보호자 확인용). 되돌리기는 그 줄을 다시 보이게 한다.
//     다시쓰기 · 표현 선택으로 문장이 바뀔 때도 서버는 옛 줄을 남긴다. 그래서 저장할 때 바뀐 이유(reason)를 같이 보낸다.
//     s.sid 는 서버의 문장 번호다 (지울 때 엉뚱한 줄을 지우지 않게 같이 보낸다). 다시쓰기 뒤에는 새 줄이라 번호가 바뀐다.
//
//   동화 주제: 새 책을 만들 때 고른다 (CreateBookPage → books.fairy_topic_id, 없으면 자유 주제).
//     글을 열면 서버가 책의 주제(entry.topic: {id, title, prompt, opening})를 알려 주고, 여기서는 보여 주기만 한다.
//     prompt 는 쓰기 안내, opening 은 시작 상황 (첫 장에서만 보여 준다).
//     주제 바꾸기는 책의 첫 문장을 쓰기 전에만 (장마다가 아니다) → PUT /api/books/{책}/topic.
//       서버가 책 전체 문장 수로 정한 entry.topic_changeable 을 따르고, 이 장에서 문장을 쓰면 바로 닫는다 (topicChangeable).
//     문장의 주제 번호(sentences.fairy_topic_id)는 서버가 책에서 넣는다 (여기서는 보내지 않는다).
//
//   동화 장: 동화 책 하나 = 이야기 하나, 이야기는 장(1장 ~ rules.story_max_chapters, 지금 100장)으로 나뉘고 장마다 글 하나다 (서버 books_repo.py '동화 장').
//     date 자리에 'ch3'(3장) · 'new'(새 장) 가 오면 그 장을 연다 (openBody). 없으면 마지막 장.
//     앞 장의 마지막 문장(prevTail)을 보여 주고, 마지막 장(100장)이면 '마지막 장' 안내를 띄운다.
//   이야기 끝내기: 3문장 이상 쓴 장이 rules.story_finish_min_chapters 개 이상이면 '이야기 끝내기'를 할 수 있다 (openFinish).
//     나갈 때(askComplete) 3·6·10장째를 채웠으면 한 번씩(rules.story_finish_ask_at), 마지막 장을 채웠으면 매번 '끝낼까요?'를 묻는다.
//     '다음에 이어 쓸래요'를 고르면 그 구간은 서버에 적어 두고 다시 묻지 않는다 (finish-later).
//     끝낸 이야기는 다시쓰기만 된다 (새 문장 · 지우기는 막는다. 서버도 막는다).
//
//   일기 하루치: 확인을 통과한 문장이 rules.diary_day_sentences(3)개가 되면 서버가 entries.day_done_at 을 적는다 (보상 기준).
//     화면에는 작은 안내(dayDoneAt)만 띄운다. 저장 버튼을 누르지 않아도 기준은 이미 채운 것이다.
//     기준을 채웠는데 '이야기 저장하기'를 안 하고 '← 목록으로'를 누르면 저장할지 한 번 묻는다 (askSave).
//     창을 그냥 닫으면 물을 수 없다 (목록에는 '쓰는 중'으로 남지만 보상 기준은 이미 채워져 있다).
//
// 쓰는 법:  const w = createWriter({ book, date, practice, onSaved, onAuthError, onDateChange })
//          w.subscribe(fn) / w.getSnapshot()  → 화면이 상태를 읽는다 (useSyncExternalStore)
//          w.boot()                          → 화면이 열릴 때 한 번
import { api, apiStream, track as trackEvent } from './api.js'

const DRAFT_DELAY_MS = 2000      // 입력을 멈추고 이만큼(1000 = 1초) 지나면 쓰던 문장을 임시저장한다
const DRAFT_MAX_WAIT_MS = 10000  // 쉬지 않고 치는 중이어도 이만큼마다 한 번은 임시저장한다 (실패했을 때 다시 해 보는 간격도 같다)
const UNDO_SECONDS = 5      // 문장을 지운 뒤 '되돌리기'를 보여 주는 시간 (초)

const track = (event, data) => trackEvent(event, data, 'write')
const short = (e) => String((e && e.message) || e).slice(0, 200)
const day10 = (v) => (v ? String(v).slice(0, 10) : null)

// 글 열기 요청 본문: 일기 날짜('2026-11-16') · 동화 장('ch3') · 새 장('new') · 없음(동화는 마지막 장)
export function openBody(target) {
    if (!target) return {}
    if (target === 'new') return { new_chapter: true }
    const m = /^ch(\d+)$/.exec(String(target))
    if (m) return { chapter: Number(m[1]) }
    return { date: target }
}

export function createWriter({ book, date, practice, onSaved, onAuthError }) {
    const dbMode = !practice
    const listeners = new Set()

    // ── 화면에 보이는 상태 ──
    const st = {
        dbMode,
        loading: dbMode,          // 글을 불러오는 중
        loadError: '',            // 글을 불러오지 못한 이유
        bookTitle: '',
        kind: 'diary',            // diary / fairy
        entry: null,              // { id, date, status }
        sentences: [],            // 쓴 문장 목록 (위에서 아래 순서)
        editingId: null,          // 다시쓰기 중인 줄의 id (없으면 새 줄 쓰기)
        insertAt: null,           // 끼워 넣을 자리 (0부터). null 이면 맨 뒤
        busy: false,              // 검사 · 교정 · 표현 선택 중이면 true (입력과 버튼을 잠근다)
        box: '',                  // 입력칸의 글
        question: '',             // 입력칸 위 안내 질문
        notice: '',               // 다시 입력 안내
        shown: '',                // 하이라이트 표시 (【 】로 감싼 글)
        choices: null,            // 개인정보 선택지 { items: [{ text, labels }], chosen: [번호|null] }
        save: { kind: '', text: '', retry: false },   // 저장 표시
        topic: '',                // 동화: 책의 주제 (제목). 빈 글자면 자유 주제
        topicId: null,            // 동화: 책의 주제 번호 (fairy_topics.id). 자유 주제면 null
        topicPrompt: '',          // 동화: 주제의 쓰기 안내 (예: 토끼가 주인공인 동화를 만들어 봐!)
        topicOpening: '',         // 동화: 주제의 시작 상황 (예: 토끼가 숲에서 … 누구의 발자국일까?). 첫 장에서만 보여 준다
        topicChangeMax: 0,        // 동화: 문장이 이 수 이하일 때만 주제를 바꿀 수 있다 (null = 언제나. 서버 TOPIC_CHANGE_MAX_SENTENCES)
        topicBookChangeable: false, // 동화: 서버가 책 전체 문장 수로 정한 '주제를 바꿀 수 있는지' (entry.topic_changeable)
        topicError: '',           // 동화: 주제를 바꾸지 못했을 때 안내
        topicBox: null,           // 동화: 주제 추천 { pick, others }
        expr: null,               // 동화: 표현 추천 { status: 'loading'|'ready'|'error', base, options, value }
        view: 'write',            // write / all(전체 글)
        storySaving: false,
        storyError: '',
        focusTick: 0,             // 바뀔 때마다 화면이 입력칸에 커서를 둔다
        scrollTo: null,           // { id, tick } 그 줄이 보이게 스크롤
        confirmDeleteId: null,    // '정말 지울까요?'를 묻고 있는 줄의 id
        deletingId: null,         // 지우는 중인 줄의 id (서버 응답을 기다리는 중)
        undo: null,               // 되돌리기 { seq, text, busy, error } (UNDO_SECONDS 동안만)
        draft: null,              // 쓰던 문장 임시저장 표시 { status: 'saved'|'error', at: 'HH:MM' } (없으면 null)
        rules: null,              // 보상 기준 숫자 (서버 reward_rules.py 의 public(). 글을 열 때 받는다)
        chapterNo: null,          // 동화: 지금 쓰는 장의 DB 번호 (글을 열 때 쓴다)
        displayNo: null,          // 동화: 화면에 보이는 장 번호 (문장을 다 지운 장을 건너뛰고 센다)
        story: null,              // 동화: 장 목록 · 끝내기 정보 (서버 _story)
        prevTail: null,           // 동화: 앞 장의 마지막 문장들 { chapter_no, sentences }
        finished: false,          // 동화: 이야기를 끝냈는지 (끝낸 뒤에는 다시쓰기만)
        finishAsk: null,          // 동화: '이야기를 끝낼까요?'를 묻고 있으면 { upto(3·6·10) | last(마지막 장) | from: 'leave' | 'button' }
        finishSaving: false,
        finishError: '',
        nextAsk: false,           // 동화: '다음 장을 쓸까요?'를 묻고 있는지
        dayDoneAt: null,          // 일기: 하루치(3문장)를 처음 채운 시각 (서버 entries.day_done_at). 있으면 작은 안내를 띄운다
        saveAsk: false,           // 일기: 나가기 전에 '저장할까요?'를 묻고 있는지
    }

    // ── 화면에 보이지 않는 상태 ──
    let snapshot = null
    let nextId = 1
    let attempt = 0             // 지금 줄에 쓴 입력 횟수 (validation_attempt)
    let tries = 0               // 이 줄을 통과하기까지 실패한 횟수
    let carried = []            // 선택지에서 이미 고른 번호들
    let reasonsNow = []         // 지금 줄이 통과하기 전에 걸린 이유들
    let lastSaved = ''          // 마지막으로 저장된 시각 (HH:MM)
    let saveChain = Promise.resolve()
    let shownTopics = []
    let topicItems = {}         // 주제 제목 → {id, title, prompt} (/api/topics 의 items)
    let exprResolve = null
    let leaving = false         // 저장하고 다른 화면으로 넘어가는 중
    let disposed = false
    let bootRun = 0             // boot 를 부른 횟수 (늦게 끝난 이전 boot 의 결과를 버리는 데 쓴다)
    let tick = 0
    let draftSent = ''          // 서버에 임시저장되어 있는 내용 (draftKey 모양). 비어 있으면 임시저장 없음
    let draftTimer = null       // 입력이 멈추기를 기다리는 타이머
    let draftWaitSince = null   // 아직 보내지 않은 글자를 처음 친 때 (DRAFT_MAX_WAIT_MS 계산용)
    let undoItem = null         // 되돌리기에 쓸 지운 줄 { s, seq } (화면에 있던 그 줄 그대로)
    let undoTimer = null

    function emit() {
        if (disposed) return
        snapshot = {
            ...st,
            // deletable: 이 줄의 '지우기'를 누를 수 있는지 (화면은 이 값만 보고 버튼을 켜고 끈다)
            sentences: st.sentences.map((s) => ({ ...s, work: s.work ? { ...s.work } : undefined, deletable: canDelete(s) })),
            save: { ...st.save },
        }
        listeners.forEach((fn) => fn())
    }
    const focus = () => { st.focusTick = (tick += 1) }
    const scrollTo = (id) => { st.scrollTo = { id, tick: (tick += 1) } }
    const written = () => st.sentences.filter((s) => s.original)

    function authFailed(e) {
        if (e && e.status === 401) { onAuthError(); return true }
        return false
    }

    // ── 저장 표시 ──
    function setSaveBar(kind, text, retry = false) {
        if (!dbMode) return
        st.save = { kind, text, retry }
    }
    function updateSaveBar() {
        if (st.sentences.some((x) => x.saveState === 'error')) setSaveBar('err', `임시저장하지 못했어요.${lastSaved ? ` 마지막 저장 ${lastSaved}` : ''}`, true)
        else setSaveBar('', lastSaved ? `임시저장했어요 · 마지막 저장 ${lastSaved}` : '')
    }

    // ── 저장 ──
    // 서버가 받는 한 줄: DB의 sentences 표와 같은 이름 (교정 항목은 파이프라인 응답 그대로)
    const payloadOf = (s) => ({
        original: s.original, revised: s.revised || s.original, attempt_count: (s.retry_count || 0) + 1,
        invalid_reasons: s.reasons || [], has_correction: !!s.was_corrected, correction_mode: s.mode || null,
        corrections: s.corrections || [], expression_choice: s.expression_choice || null,
        reason: s.reason || null,   // 이미 있던 줄이 바뀐 이유: edit 다시쓰기 / expr 표현 선택 (서버가 옛 줄을 기록으로 남긴다)
    })

    async function saveOne(s) {
        const seq = st.sentences.indexOf(s) + 1
        if (seq < 1 || !s.original) return true
        s.saveState = 'saving'
        try {
            // 끼워 넣은 문장은 그 자리부터 뒤 문장을 한 칸씩 미는 주소로, 나머지는 그 순서에 덮어쓰는 주소로 보낸다
            const base = `/api/entries/${st.entry.id}/sentences/${seq}`
            const r = s.inserted ? await api(`${base}/insert`, { method: 'POST', body: payloadOf(s) })
                                                      : await api(base, { method: 'PUT', body: payloadOf(s) })
            s.saveState = 'saved'
            s.inserted = false
            s.reason = null
            if (r.sentence_id) s.sid = r.sentence_id        // 내용이 바뀌면 서버는 새 줄을 만든다 → 번호가 바뀐다
            if (r.changed) { draftSent = ''; st.draft = null }   // 문장이 저장되면 서버가 임시저장을 비운다
            st.entry.status = r.entry.status
            if (r.entry.day_done_at) st.dayDoneAt = r.entry.day_done_at   // 일기 하루치를 이번에(또는 전에) 채웠다
            if (r.day_done) track('day_done', { entry: st.entry.id, sentences: written().length })
            lastSaved = String(r.saved_at || '').slice(11, 16)
            return true
        } catch (e) {
            s.saveState = 'error'
            track('save_fail', { seq, message: short(e) })
            authFailed(e)
            return false
        }
    }

    function queueSave(s) {
        if (!dbMode || !st.entry) return Promise.resolve(true)
        setSaveBar('', '저장 중…')
        saveChain = saveChain.then(async () => {
            const ok = await saveOne(s)
            updateSaveBar()
            emit()
            return ok
        })
        const saved = saveChain                           // 이 문장의 저장 결과 (부른 쪽이 기다린다)
        syncDraft(true)                                   // 문장 저장 뒤에 임시저장 상태를 맞춘다 (같은 문장이라 서버가 안 비운 경우 등)
        return saved
    }

    // ── 쓰던 문장 임시저장 ──
    // 지금 임시저장되어 있어야 할 내용: 입력칸의 글자 + 어느 자리의 것인지
    function draftNow() {
        if (!st.box.trim()) return { text: '', mode: 'new', seq: null }
        const editAt = st.sentences.findIndex((x) => x.id === st.editingId)
        if (editAt >= 0) return { text: st.box, mode: 'edit', seq: editAt + 1 }
        if (st.insertAt !== null && st.insertAt < st.sentences.length) return { text: st.box, mode: 'insert', seq: st.insertAt + 1 }
        return { text: st.box, mode: 'new', seq: null }
    }
    const draftKey = (d) => (d.text ? JSON.stringify([d.text, d.mode, d.seq]) : '')
    const draftSafe = () => draftKey(draftNow()) === draftSent   // 입력칸의 글자가 이미 서버에 임시저장되어 있는지

    // 지금 서버로 보낼 임시저장 내용. 보내면 안 되는 때는 null.
    function draftToSend(fixed) {
        if (leaving) return null                          // '이야기 저장하기'로 넘어가는 중이면 건드리지 않는다
        if (!fixed && st.busy && !st.box.trim()) return null   // 교정 중: 입력칸은 비었지만 그 문장은 아직 저장 전이다 → 임시저장을 남겨 둔다
        const d = fixed || draftNow()
        // 저장하지 못한 문장이 있으면 임시저장을 지우지 않는다 (그 문장의 마지막 보관본일 수 있다)
        if (!d.text && st.sentences.some((x) => x.original && x.saveState !== 'saved')) return null
        return draftKey(d) === draftSent ? null : d
    }

    async function sendDraft(d, keepalive = false) {
        const key = draftKey(d)
        try {
            const r = await api(`/api/entries/${st.entry.id}/draft`, { method: 'PUT', body: d, keepalive })
            draftSent = key
            st.draft = d.text ? { status: 'saved', at: String(r.saved_at || '').slice(11, 16) } : null
        } catch (e) {
            if (authFailed(e)) return
            st.draft = d.text ? { status: 'error', at: st.draft ? st.draft.at : '' } : st.draft
            // 실패하면 DRAFT_MAX_WAIT_MS 뒤에 다시 해 본다 (그 사이 다시 치면 그때 보낸다)
            if (!disposed && !draftTimer) draftTimer = setTimeout(() => { draftTimer = null; syncDraft(true) }, DRAFT_MAX_WAIT_MS)
        }
        emit()                                            // 저장 표시와 나가기 전 안내(unsavedWork)가 바뀐다
    }

    // 서버의 임시저장을 지금 상태에 맞춘다. now 가 아니면 입력이 멈추기를 기다렸다가 한다
    // (멈추지 않고 계속 쳐도 DRAFT_MAX_WAIT_MS 가 지나면 보낸다).
    // 문장 저장과 같은 줄(saveChain)에 세워서, 문장 저장 → 임시저장 순서가 뒤바뀌지 않게 한다.
    // fixed 를 주면 '지금 상태' 대신 그 내용을 저장한다 (확인하기를 누른 순간의 글자: 차례가 올 때쯤엔 입력칸이 비어 있을 수 있다).
    function syncDraft(now, fixed = null) {
        if (!dbMode || !st.entry || disposed) return
        clearTimeout(draftTimer)
        draftTimer = null
        if (!now) {
            if (draftWaitSince === null) draftWaitSince = Date.now()
            const left = DRAFT_MAX_WAIT_MS - (Date.now() - draftWaitSince)
            draftTimer = setTimeout(() => { draftTimer = null; syncDraft(true) }, Math.max(0, Math.min(DRAFT_DELAY_MS, left)))
            return
        }
        draftWaitSince = null
        saveChain = saveChain.then(async () => {
            const d = draftToSend(fixed)
            if (d) await sendDraft(d)
        })
    }

    // 화면이 가려질 때(다른 앱으로 넘어감 · 화면 꺼짐 · 탭 닫힘): 기다리지 않고 지금 바로 보낸다.
    // 태블릿에서는 이때 페이지가 그대로 멈추거나 정리될 수 있어서, 줄(saveChain)을 기다리지 않고 keepalive 로 보낸다.
    function flushDraft() {
        if (!dbMode || !st.entry || disposed) return
        clearTimeout(draftTimer)
        draftTimer = null
        draftWaitSince = null
        const d = draftToSend(null)
        if (d) { track('draft_flush', { chars: d.text.length }); sendDraft(d, true) }
    }

    // 저장되지 않은 줄을 앞에서부터 다시 저장한다 (앞 줄이 실패하면 거기서 멈춘다: 순서가 비면 서버가 받지 않는다)
    async function retrySaves() {
        setSaveBar('', '저장 중…')
        emit()
        saveChain = saveChain.then(async () => {
            for (const s of st.sentences) {
                if (s.original && s.saveState !== 'saved') {
                    if (!(await saveOne(s))) break
                }
            }
            updateSaveBar()
            emit()
        })
        await saveChain
        return !st.sentences.some((x) => x.original && x.saveState !== 'saved')
    }

    const fromServer = (x) => ({
        id: nextId++, sid: x.id, original: x.original, revised: x.revised, retry_count: Math.max(0, (x.attempt_count || 1) - 1),
        was_corrected: !!x.has_correction, corrections: x.corrections || [], compliment: null, mode: x.correction_mode,
        reasons: x.invalid_reasons || [], expression_choice: x.expression_choice || null, saveState: 'saved',
    })

    // ── 질문 ──
    // 검사에 보내는 이전 문장: 통과한 문장들 중, 지금 다시쓰는 줄은 뺀다 (안 빼면 "방금과 같은 문장"으로 걸러진다)
    const previousFor = () => st.sentences.filter((s) => s.original && s.id !== st.editingId).map((s) => s.original)

    async function loadQuestion() {
        try {
            const topic = st.topic ? `&topic=${encodeURIComponent(st.topic)}` : ''
            const r = await api(`/question?passed=${previousFor().length}&kind=${st.kind}${topic}`)
            st.question = r.question
            emit()
        } catch {
            // 질문을 못 불러와도 글쓰기는 그대로 할 수 있다
        }
    }

    // ── 동화 주제 ──
    // 주제는 책에 있다 (새 책 만들기에서 고름). 이 화면에서는 책의 첫 문장을 쓰기 전에만 바꿀 수 있다 (topicChangeable).
    // 서버 값(책 전체 문장 수로 본 것)을 따르고, 이 장에 방금 쓴 문장도 센다. 2장 이후의 빈 장에서는 서버 값이 false 라 버튼이 안 보인다.
    function topicChangeable() {
        if (st.kind !== 'fairy' || !st.entry || !st.topicBookChangeable) return false
        return st.topicChangeMax === null || written().length <= st.topicChangeMax
    }
    function setTopic(t) {
        st.topic = t ? t.title : ''
        st.topicId = t && Number.isInteger(t.id) ? t.id : null
        st.topicPrompt = t && t.prompt ? t.prompt : ''
        st.topicOpening = t && t.opening ? t.opening : ''
    }

    async function openTopics(more) {
        if (!topicChangeable()) return
        if (!more) shownTopics = []
        let r
        try {
            r = await api(`/api/topics?exclude=${encodeURIComponent(shownTopics.join(','))}`)
        } catch (e) {
            authFailed(e)
            return                                          // 추천을 못 받아도 글쓰기는 그대로 할 수 있다
        }
        for (const t of r.items || []) topicItems[t.title] = t
        st.topicError = ''
        shownTopics = shownTopics.concat([r.pick], r.others)
        track(more ? 'topic_more' : 'topic_open', { pick: r.pick, others: r.others })
        st.topicBox = { pick: r.pick, others: r.others }
        emit()
    }

    // 주제 바꾸기 (v: 주제 이름, 빈 글자 = 내가 정할래요). 책에 저장한 뒤 화면에 반영한다.
    // 이미 첫 문장을 썼으면 서버가 400 으로 막는다 (그 사이 다른 기기에서 썼을 때).
    async function chooseTopic(v) {
        const t = v ? (topicItems[v] || { id: null, title: v, prompt: null, opening: null }) : null
        if (dbMode) {
            let r
            try {
                r = await api(`/api/books/${encodeURIComponent(book)}/topic`, { method: 'PUT', body: { fairy_topic_id: t && Number.isInteger(t.id) ? t.id : null } })
            } catch (e) {
                if (authFailed(e)) return
                st.topicError = e.message || '주제를 바꾸지 못했어요. 다시 해 볼까요?'
                emit()
                return
            }
            setTopic(r.topic)
        } else {
            setTopic(t)
        }
        track(v ? 'topic_pick' : 'topic_skip', v ? { topic: v, topic_id: st.topicId, shown: shownTopics.length } : { shown: shownTopics.length })
        st.topicBox = null
        st.topicError = ''
        focus()
        emit()
        loadQuestion()
    }
    function closeTopics() {
        st.topicBox = null
        st.topicError = ''
        emit()
    }

    // ── 열기 ──
    async function boot() {
        disposed = false                                  // 화면이 다시 붙은 경우 (개발 모드의 StrictMode 는 화면을 한 번 뗐다 붙인다)
        const run = (bootRun += 1)
        if (!dbMode) {
            track('page_open', { mode: 'practice' })
            emit()
            loadQuestion()
            return
        }
        st.loading = true
        st.loadError = ''
        st.busy = true
        emit()
        try {
            const r = await api(`/api/books/${encodeURIComponent(book)}/entries`, { method: 'POST', body: openBody(date) })
            if (disposed || run !== bootRun) return
            st.entry = { id: r.entry.id, date: day10(r.entry.date), status: r.entry.status }
            st.bookTitle = r.book.title
            st.kind = r.book.kind === 'fairy' ? 'fairy' : 'diary'
            st.sentences = r.sentences.map(fromServer)
            st.rules = r.rules || null
            st.loading = false
            st.busy = false
            restoreDraft(r.entry)
            st.dayDoneAt = r.entry.day_done_at || null
            if (st.kind === 'fairy') {                      // 동화: 책의 주제 (새 책 만들기에서 고름. 없으면 자유 주제) · 장
                setTopic(r.entry.topic || null)
                st.topicChangeMax = r.entry.topic_change_max === undefined ? 0 : r.entry.topic_change_max
                st.topicBookChangeable = !!r.entry.topic_changeable
                st.chapterNo = r.entry.chapter_no || 1
                st.displayNo = r.entry.display_no || st.chapterNo
                st.story = r.story || null
                st.prevTail = r.prev_tail || null
                st.finished = !!(r.story && r.story.finished)
            }
            track('page_open', { mode: 'db', book, date, entry: st.entry.id, kind: st.kind, status: st.entry.status, sentences: st.sentences.length })
            focus()
            emit()
            loadQuestion()
        } catch (e) {
            if (disposed || run !== bootRun || authFailed(e)) return
            track('open_fail', { book, date, message: short(e) })
            st.loading = false
            st.loadError = e.message
            emit()
        }
    }

    // 임시저장된 '쓰던 문장'을 입력칸에 되살린다. 다시쓰기 · 위에 넣기 중이었다면 그 상태로 돌아간다.
    // 그 자리의 문장이 이제 없으면(다른 곳에서 글이 바뀐 경우) 새 문장으로만 되살린다.
    function restoreDraft(entry) {
        const text = typeof entry.draft_text === 'string' ? entry.draft_text : ''
        if (!text.trim()) return
        const at = Number(entry.draft_seq) - 1
        const inRange = Number.isInteger(at) && at >= 0 && at < st.sentences.length
        st.box = text
        if (entry.draft_mode === 'edit' && inRange) st.editingId = st.sentences[at].id
        else if (entry.draft_mode === 'insert' && inRange) st.insertAt = at
        st.notice = '쓰다가 멈춘 문장을 불러왔어요.'
        st.draft = { status: 'saved', at: String(entry.draft_saved_at || '').slice(11, 16) }
        const mode = entry.draft_mode === 'edit' || entry.draft_mode === 'insert' ? entry.draft_mode : 'new'
        draftSent = draftKey({ text, mode, seq: mode === 'new' ? null : Number(entry.draft_seq) })   // 서버에 있는 그대로
        if (!draftSafe()) syncDraft(false)                // 자리가 사라져 새 문장으로 되살린 경우: 서버 쪽도 맞춘다
        track('draft_restore', { chars: text.length, mode: entry.draft_mode || 'new', kept: draftNow().mode })
    }

    // ── 입력 안내 ──
    function clearNotice() { st.notice = ''; st.shown = ''; st.choices = null }

    function mark(text, spans) {                        // 하이라이트 구간을 【 】로 감싼다 (뒤에서부터 바꿔야 위치가 어긋나지 않는다)
        let out = text
        ;[...spans].sort((a, b) => b.start - a.start).forEach((s) => {
            out = `${out.slice(0, s.start)}【${out.slice(s.start, s.end)}】${out.slice(s.end)}`
        })
        return out
    }

    function resetLine() { attempt = 0; carried = []; tries = 0; reasonsNow = [] }

    // ── 다시쓰기 · 끼워 넣기 · 순서 바꾸기 ──
    function startEdit(id) {
        if (st.busy || st.deletingId !== null) return
        st.insertAt = null
        track('edit_start', { seq: st.sentences.findIndex((x) => x.id === id) + 1 })
        st.editingId = id
        resetLine(); clearNotice(); st.box = ''
        scrollTo(id); focus(); emit()
        syncDraft(false)
        loadQuestion()
    }

    function cancelEdit() {
        if (st.busy) return
        track('edit_cancel', { editing: st.editingId !== null, inserting: st.insertAt !== null })
        st.insertAt = null
        st.editingId = null
        resetLine(); clearNotice(); st.box = ''
        focus(); emit()
        syncDraft(false)
        loadQuestion()
    }

    function startInsert(id) {
        if (st.busy || st.deletingId !== null || st.finished) return
        const i = st.sentences.findIndex((x) => x.id === id)
        if (i < 0) return
        track('insert_start', { at: i + 1 })
        st.editingId = null
        st.insertAt = i
        resetLine(); clearNotice(); st.box = ''
        focus(); emit()
        syncDraft(false)
        loadQuestion()
    }

    function moveSentence(id, dir) {
        if (st.busy || st.deletingId !== null || st.finished) return
        const i = st.sentences.findIndex((x) => x.id === id)
        const j = i + dir
        if (i < 0 || j < 0 || j >= st.sentences.length) return
        if (dbMode && st.sentences.some((x) => x.original && x.saveState !== 'saved')) {
            st.notice = '저장이 끝난 뒤에 순서를 바꿀 수 있어요.'
            emit()
            return
        }
        const a = st.sentences[i]
        const b = st.sentences[j]
        track('move', { from: i + 1, to: j + 1 })
        clearNotice(); st.editingId = null; st.insertAt = null
        st.sentences[i] = b
        st.sentences[j] = a
        scrollTo(a.id)
        if (!dbMode || !st.entry) { emit(); return }
        setSaveBar('', '저장 중…')
        emit()
        saveChain = saveChain.then(async () => {
            try {
                const r = await api(`/api/entries/${st.entry.id}/sentences/${i + 1}/move`, { method: 'POST', body: { to: j + 1 } })
                st.entry.status = r.entry.status
                lastSaved = String(r.saved_at || '').slice(11, 16)
                updateSaveBar()
            } catch (e) {                                   // 실패: 화면의 순서를 되돌린다 (서버와 화면이 어긋나지 않게)
                const x = st.sentences.indexOf(a)
                const y = st.sentences.indexOf(b)
                if (x >= 0 && y >= 0) { st.sentences[x] = b; st.sentences[y] = a }
                setSaveBar('err', `순서를 바꾸지 못했어요. ${e.message}`)
                track('move_fail', { from: i + 1, to: j + 1, message: short(e) })
                authFailed(e)
            }
            emit()
        })
        syncDraft(true)                                   // 순서를 바꾸면 다시쓰기 · 넣기 상태가 풀린다 → 쓰던 문장을 새 문장으로 맞춰 둔다
    }

    // ── 교정 (스트림) ──
    function onEvent(ev, s) {
        const w = s.work
        if (ev.type === 'stage') { w.progress = `${ev.label}…`; w.loadingSince = null }
        else if (ev.type === 'loading') { w.progress = `${ev.label} (처음에는 몇 분 걸릴 수 있어요)`; w.loadingSince = Date.now() }
        else if (ev.type === 'update') {
            const d = ev.data
            if ('revised_sentence' in d) w.revised = d.revised_sentence
            if ('difference' in d) w.diff = d.difference
            if ('explanations' in d) w.exps = d.explanations
            if ('compliment' in d) w.compliment = d.compliment
        } else if (ev.type === 'done') {
            const c = ev.correction                         // 교정 결과 (original_sentence, revised_sentence, corrections[], compliment ...)
            s.original = c.original_sentence
            s.revised = c.revised_sentence
            s.corrections = c.corrections || []
            s.compliment = c.compliment || null
            s.was_corrected = !!c.has_correction
            s.retry_count = w.tries
            s.reasons = w.reasons || []                     // 이 줄을 통과하기 전에 걸린 이유들
            s.expression_choice = null                      // 문장이 바뀌었으니 앞서 고른 표현 기록은 지운다
            s.saveState = 'pending'                         // 저장 대기 (교정이 끝나면 handle 이 저장한다)
            s.mode = ev.mode
            s.openFix = true                                // 방금 고친 줄은 펼쳐 둔다
            delete s.work
        } else if (ev.type === 'error') {
            w.status = 'error'
            w.error = `교정 중에 문제가 생겼어요: ${ev.message}`
        }
        emit()
    }

    async function runCorrection(s) {
        try {
            await apiStream('/correct', { original_sentence: s.work.original }, (ev) => onEvent(ev, s))
            if (s.work && s.work.status !== 'error') onEvent({ type: 'error', message: '응답이 중간에 끊겼어요' }, s)
        } catch (e) {
            if (s.work) onEvent({ type: 'error', message: short(e) }, s)
        }
    }

    // ── 동화 표현 추천 ──
    // 문장이 교정까지 끝나고 저장된 뒤에, 다르게 쓴 문장 몇 개와 '원래 문장 그대로'를 보여 준다.
    // 고르면 그 문장으로 바꿔 다시 저장한다. 추천이 없으면 아무것도 띄우지 않고, 불러오지 못해도 쓴 문장은 그대로다.
    // 서버(/suggest)가 보기마다 {text, point}(무엇이 좋아졌는지 한 줄)를 준다. 모델이 꺼져 있으면 demo=True 와 안내(notice)가 온다.
    // 맞춤법을 고친 문장에도 추천할지는 서버 설정(STORY_SUGGEST_ON)이 정한다. 추천하지 않으면 빈 목록이 온다.
    function offerExpressions(s) {
        return new Promise((resolve) => {
            const base = s.revised || s.original
            exprResolve = () => { st.expr = null; exprResolve = null; resolve() }
            const load = async () => {
                st.expr = { status: 'loading', base, options: [], value: 'keep', sentenceId: s.id, load }
                emit()
                let r
                try {
                    r = await api('/suggest', { method: 'POST', body: { sentence: base, has_correction: !!s.was_corrected } })
                } catch (e) {
                    track('expr_fail', { message: short(e) })
                    st.expr = { ...st.expr, status: 'error' }
                    emit()
                    return
                }
                // 보기: 문자열(예전 형식)이든 {text, point} 든 받아서 {text, point} 로 맞춘다. 원래 문장과 같거나 겹치는 보기는 뺀다
                const options = []
                for (const o of r.options || []) {
                    const text = String((typeof o === 'string' ? o : o && o.text) || '').trim()
                    const point = typeof o === 'string' ? '' : String((o && o.point) || '').trim()
                    if (text && text !== base && !options.some((x) => x.text === text)) options.push({ text, point })
                }
                options.splice(3)
                track('expr_shown', { options: options.length, demo: !!r.demo, skipped: r.skipped || null })
                if (!options.length) { exprResolve(); emit(); return }
                st.expr = {
                    ...st.expr, status: 'ready', options,
                    guide: r.guide || '', originalPoint: r.original_point || '',
                    demo: !!r.demo, notice: r.notice || '',     // 모델이 꺼져 있을 때: 임시 예시라는 안내 (화면에 꼭 보여 준다)
                }
                emit()
            }
            load()
        })
    }

    function pickExpr(value) { if (st.expr) { st.expr = { ...st.expr, value }; emit() } }
    function retryExpr() { if (st.expr && st.expr.load) st.expr.load() }
    function skipExpr() { if (exprResolve) { exprResolve(); emit() } }

    function confirmExpr() {
        const e = st.expr
        if (!e || e.status !== 'ready') return
        const s = st.sentences.find((x) => x.id === e.sentenceId)
        const picked = e.value !== 'keep' ? e.options[Number(e.value)].text : null
        track('expr_pick', { picked: picked ? Number(e.value) : null, options: e.options.length, demo: !!e.demo })
        if (s) {
            // 무엇을 보여 줬고 무엇을 골랐는지 (DB의 expression_choice). base · options(문장 목록) · picked 는 대시보드가 읽으므로 모양을 유지하고,
            // points(보기마다 한 줄 설명) · demo(모델이 꺼져 임시 예시였는지)를 덧붙인다
            s.expression_choice = { base: e.base, options: e.options.map((o) => o.text), points: e.options.map((o) => o.point), picked, demo: !!e.demo }
            if (picked) { s.revised = picked; s.reason = 'expr' }   // 표현을 바꾸면 서버가 바뀌기 전 줄을 기록으로 남긴다
            s.saveState = 'pending'
            if (dbMode) queueSave(s)
        }
        exprResolve()
        st.notice = picked ? '잘했어요! 내 뜻에 맞는 표현을 골랐어요.' : ''
        emit()
    }

    // ── 검사 ──
    async function send(picks) {
        const body = { user_input: st.box, validation_attempt: attempt, previous_sentences: previousFor(), choice_picks: picks, kind: st.kind }
        const r = await api('/validate', { method: 'POST', body })
        track('validate', { attempt: body.validation_attempt, chars: body.user_input.length, route: r.route, valid: !!r.is_valid,
                                                awaiting_choice: !!r.awaiting_choice, editing: st.editingId !== null, inserting: st.insertAt !== null, picks: (picks || []).length })
        return r
    }

    async function handle(r) {
        attempt = r.validation_attempt
        clearNotice()

        if (r.route === 'correction') {
            carried = []
            let s = st.sentences.find((x) => x.id === st.editingId)
            if (s) s.reason = 'edit'                        // 다시쓰기: 서버가 옛 줄을 기록으로 남긴다
            if (!s) {                                       // 새 줄: 맨 뒤에 붙이거나, 고른 자리에 끼워 넣는다
                s = { id: nextId++ }
                if (st.insertAt !== null && st.insertAt < st.sentences.length) { s.inserted = true; st.sentences.splice(st.insertAt, 0, s) }
                else st.sentences.push(s)
            }
            const wasEditing = st.editingId                 // 교정이 실패하면 이 상태로 되돌린다
            const wasInsertAt = s.inserted ? st.sentences.indexOf(s) : null
            st.insertAt = null
            s.work = { original: r.original_sentence, progress: '교정을 시작해요…', tries, reasons: reasonsNow.slice() }
            reasonsNow = []
            st.box = ''
            st.sentences.forEach((x) => { x.openFix = false })   // 이전 줄들의 '고친 곳'은 접어 둔다
            st.busy = true
            scrollTo(s.id)
            emit()
            await runCorrection(s)
            if (dbMode && s.saveState === 'pending') queueSave(s)                          // 교정이 끝난 문장을 바로 임시저장
            if (st.kind === 'fairy' && s.original && !s.work) await offerExpressions(s)    // 동화: 다르게 쓴 표현을 고르게 한다
            st.busy = false
            st.editingId = null
            if (s.work && s.work.status === 'error') {      // 실패: 새 줄이었다면 목록에서 치우고 입력으로 돌려준다 (다시쓰기였다면 기존 문장 유지)
                const msg = `${s.work.error} 다시 시도해 주세요.`
                if (!s.original) st.sentences = st.sentences.filter((x) => x.id !== s.id)
                else delete s.work
                st.notice = msg
                st.box = r.original_sentence
                // 쓰던 자리로 되돌린다 (다시쓰기였으면 그 줄, 위에 넣기였으면 그 자리). 임시저장도 그대로 남아 있다
                if (st.sentences.some((x) => x.id === wasEditing)) st.editingId = wasEditing
                else if (wasInsertAt !== null && wasInsertAt < st.sentences.length) st.insertAt = wasInsertAt
            }
            attempt = 0
            tries = 0
            scrollTo(s.id); focus(); emit()
            loadQuestion()
            return
        }

        tries += 1                                        // 통과하지 못한 제출
        if (!r.awaiting_choice) reasonsNow.push(...(r.validation_log || []).filter((l) => !String(l).startsWith('[확인용]')))
        st.notice = r.retry_message || ''
        if (r.highlights && r.highlights.length) st.shown = mark(r.display_text, r.highlights)

        if (r.awaiting_choice) {                          // 개인정보를 바꿀 말 고르기
            tries -= 1                                      // 선택은 실패가 아니다
            st.choices = { items: r.highlights.map((hl) => ({ text: hl.text, labels: hl.choices })), chosen: r.highlights.map(() => null) }
            return
        }
        carried = []
        if (r.route === 'skipped') {                      // 3번 실패: 이 줄 건너뜀
            st.box = ''
            if (st.editingId !== null) {                    // 다시쓰기였다면 기존 문장을 그대로 둔다
                st.notice = `${r.retry_message || ''} 기존 문장을 그대로 두었어요.`
                st.editingId = null
                resetLine()
                loadQuestion()
            } else { tries = 0; reasonsNow = []; st.insertAt = null }
        }
    }

    async function run(picks) {
        st.busy = true
        emit()
        try {
            await handle(await send(picks))
        } catch (e) {
            if (!authFailed(e)) st.notice = `검사 중에 문제가 생겼어요: ${short(e)}`
        }
        st.busy = false
        if (st.view === 'write') focus()
        emit()
        syncDraft(true)                                   // 결과에 맞춘다: 건너뛴 줄이면 지우고, 다시 써야 하면 그대로 둔다
    }

    function submit() {
        if (st.busy || st.deletingId !== null) return
        if (st.finished && st.editingId === null) {        // 끝낸 이야기: 새 문장은 쓸 수 없다 (다시쓰기만)
            st.notice = '끝낸 이야기는 고쳐 쓰기만 할 수 있어요. 고칠 문장의 다시쓰기를 눌러 주세요.'
            emit()
            return
        }
        carried = []
        syncDraft(true, draftNow())                       // 검사 · 교정에 들어가기 전에 쓴 문장을 먼저 임시저장한다
        run([])
    }

    function choose(i, n) {
        if (st.busy || !st.choices) return
        const chosen = st.choices.chosen.slice()
        chosen[i] = n
        st.choices = { ...st.choices, chosen }
        if (chosen.every((v) => v !== null)) {
            carried = carried.concat(chosen)
            run(carried)
        } else emit()
    }

    // ── 문장 지우기 · 되돌리기 ──
    // 지울 수 있는 줄: 저장이 끝난 줄. 다시쓰기 중인 줄, 검사 · 교정 · 표현 선택 중, 다른 줄을 지우는 중에는 못 지운다.
    // 저장이 안 된 줄이 하나라도 있으면 막는다 (지우면 뒤 줄의 순서가 바뀌는데, 저장 안 된 줄은 순서로 저장되기 때문).
    function canDelete(s) {
        return dbMode && !!st.entry && !st.finished && !st.busy && !st.expr && st.view === 'write' && st.deletingId === null
            && !!s && !!s.sid && s.saveState === 'saved' && !s.work && s.id !== st.editingId
            && !st.sentences.some((x) => x.original && x.saveState !== 'saved')
    }

    function askDelete(id) {
        const s = st.sentences.find((x) => x.id === id)
        if (!canDelete(s)) return
        track('delete_ask', { seq: st.sentences.indexOf(s) + 1 })
        st.confirmDeleteId = id
        emit()
    }

    function cancelDelete() {
        if (st.confirmDeleteId === null) return
        track('delete_cancel')
        st.confirmDeleteId = null
        focus(); emit()
    }

    function clearUndo() {
        clearTimeout(undoTimer)
        undoTimer = null
        undoItem = null
        st.undo = null
    }

    function confirmDelete() {
        const s = st.sentences.find((x) => x.id === st.confirmDeleteId)
        st.confirmDeleteId = null
        if (!canDelete(s)) { emit(); return }
        const seq = st.sentences.indexOf(s) + 1
        st.deletingId = s.id
        clearNotice()
        setSaveBar('', '지우는 중…')
        emit()
        saveChain = saveChain.then(async () => {
            try {
                const r = await api(`/api/entries/${st.entry.id}/sentences/${seq}?sentence_id=${s.sid}`, { method: 'DELETE' })
                const i = st.sentences.indexOf(s)
                if (i >= 0) {
                    st.sentences.splice(i, 1)
                    // 위에 넣기 중이었다면 넣을 자리를 맞춘다 (서버도 쓰던 문장의 자리를 같은 규칙으로 맞춘다)
                    if (st.insertAt !== null && st.insertAt > i) st.insertAt -= 1
                    if (st.insertAt !== null && st.insertAt >= st.sentences.length) st.insertAt = null
                }
                st.entry.status = r.entry.status
                lastSaved = String(r.saved_at || '').slice(11, 16)
                updateSaveBar()
                track('delete_done', { seq })
                clearUndo()                                 // 되돌리기는 마지막에 지운 한 줄만
                undoItem = { s, seq }
                st.undo = { seq, text: s.revised || s.original, busy: false, error: false }
                undoTimer = setTimeout(() => { if (st.undo && !st.undo.busy) { clearUndo(); emit() } }, UNDO_SECONDS * 1000)
            } catch (e) {
                if (!authFailed(e)) {
                    setSaveBar('err', e.status === 409 ? e.message : `문장을 지우지 못했어요. 다시 해 주세요. (${short(e)})`)
                    track('delete_fail', { seq, status: e.status || 0 })
                }
            }
            st.deletingId = null
            emit()
        })
        syncDraft(true)                                   // 쓰던 문장의 자리가 바뀌었을 수 있다 → 서버와 맞춰 둔다
    }

    function undoDelete() {
        const item = undoItem
        if (!item || !st.undo || st.undo.busy || st.busy || st.deletingId !== null) return
        st.undo = { ...st.undo, busy: true, error: false }
        emit()
        saveChain = saveChain.then(async () => {
            try {
                const r = await api(`/api/entries/${st.entry.id}/restore`, { method: 'POST', body: { sentence_id: item.s.sid, seq: item.seq } })
                if (undoItem === item) {
                    const at = Math.min(Math.max(1, r.seq), st.sentences.length + 1) - 1
                    if (!st.sentences.includes(item.s)) st.sentences.splice(at, 0, item.s)
                    if (st.insertAt !== null && st.insertAt >= at) st.insertAt += 1
                    st.entry.status = r.entry.status
                    if (r.day_done && !st.dayDoneAt) st.dayDoneAt = r.saved_at   // 되살려서 일기 하루치를 채웠다
                    if (r.saved_at) lastSaved = String(r.saved_at).slice(11, 16)
                    updateSaveBar()
                    track('delete_undo', { seq: r.seq })
                    clearUndo()
                    scrollTo(item.s.id)
                }
            } catch (e) {
                if (!authFailed(e) && undoItem === item) {
                    st.undo = { ...st.undo, busy: false, error: true }
                    clearTimeout(undoTimer)                 // 실패하면 '다시 시도'를 UNDO_SECONDS 동안 더 보여 준다
                    undoTimer = setTimeout(() => { if (st.undo && !st.undo.busy) { clearUndo(); emit() } }, UNDO_SECONDS * 1000)
                    track('delete_undo_fail', { status: e.status || 0 })
                }
            }
            emit()
        })
        syncDraft(true)
    }

    // ── 전체 글 · 이야기 저장하기 ──
    function finish() {
        track('finish_click', { sentences: written().length })
        st.view = 'all'
        emit()
    }

    function backToWrite() {
        track('back_to_write')
        st.view = 'write'
        st.storyError = ''
        focus(); emit()
    }

    function restart() {                                // 연습 모드 전용: 처음부터 다시 쓰기
        st.sentences = []
        st.editingId = null
        resetLine(); clearNotice()
        st.view = 'write'
        emit()
        loadQuestion()
    }

    // '이야기 저장하기': 저장 안 된 문장을 먼저 모두 저장하고 → 글을 '완성'으로 → 글 보기 화면(저장했어요!)으로 넘어간다
    async function saveStory() {
        if (st.storySaving) return
        st.storySaving = true
        st.storyError = ''
        emit()
        try {
            if (!(await retrySaves())) throw new Error('저장되지 않은 문장이 있어요.')
            await api(`/api/entries/${st.entry.id}/complete`, { method: 'POST' })
            track('story_saved', { entry: st.entry.id, sentences: written().length })
            leaving = true
            onSaved(st.entry.id)
        } catch (e) {
            if (authFailed(e)) return
            st.storyError = `이야기를 저장하지 못했어요. 쓴 이야기는 그대로 있어요. (${e.message})`
            st.storySaving = false
            track('story_save_fail', { entry: st.entry ? st.entry.id : null, message: short(e) })
            emit()
        }
    }

    // ── 이전 장 · 다음 장 (동화) ──
    // 글쓰기 화면에서 장 사이를 오간다. 이미 있는 장으로는 바로, 새 장은 먼저 묻는다 (askNext).
    // 문장을 다 지운 장은 건너뛴다. 끝낸 이야기도 있는 장끼리는 오갈 수 있다 (새 장은 안 된다).
    // 돌려주는 값: { prev, next } 각각 { target: 'ch4'(App 의 writeDate 자리), isNew: 새로 만드는 장인지, display: 화면 번호 } 또는 null
    // 'new' 대신 장 번호로 넘기는 이유: 'new' 로 연 장에서 다시 'new' 를 넘기면 App 의 key 가 같아 화면이 새로 열리지 않는다.
    // (서버는 문장이 있는 마지막 장의 바로 다음 번호면 그 장을 만든다)
    function chapterNav() {
        const none = { prev: null, next: null }
        if (!dbMode || st.kind !== 'fairy' || !st.entry) return none
        const all = st.story ? st.story.chapters : []
        const shown = all.filter((c) => c.sentence_count > 0 || c.chapter_no === st.chapterNo)
        const i = shown.findIndex((c) => c.chapter_no === st.chapterNo)
        const go = (c) => ({ target: `ch${c.chapter_no}`, isNew: false, display: c.display_no })
        const prev = i > 0 ? go(shown[i - 1]) : null
        let next = i >= 0 && i < shown.length - 1 ? go(shown[i + 1]) : null
        if (!next && !st.finished && written().length > 0) {          // 마지막 장: 문장이 있으면 새 장 (rules.story_max_chapters 까지)
            const max = st.rules ? st.rules.story_max_chapters : 100
            const writtenChapters = all.filter((c) => c.sentence_count > 0 && c.chapter_no !== st.chapterNo).length + 1
            if (writtenChapters < max) {
                const emptyAfter = all.find((c) => c.chapter_no > st.chapterNo && c.sentence_count === 0)   // 뒤에 비어 있는 장이 있으면 그 장에 쓴다
                const lastNo = Math.max(st.chapterNo, ...all.map((c) => c.chapter_no))
                next = { target: `ch${emptyAfter ? emptyAfter.chapter_no : lastNo + 1}`, isNew: true, display: (st.displayNo || 1) + 1 }
            }
        }
        return { prev, next }
    }
    function askNext() {
        if (st.busy || !chapterNav().next) return
        track('next_chapter_ask', { chapter: st.chapterNo })
        st.nextAsk = true
        emit()
    }
    function closeNext() {
        if (!st.nextAsk) return
        st.nextAsk = false
        emit()
    }

    // ── 이야기 끝내기 (동화) ──
    // 장별 문장 수: 지금 장은 화면에 쓴 문장 수로 센다 (방금 쓴 문장까지 바로 반영)
    function storyQualified() {
        const rules = st.rules || {}
        const min = rules.story_chapter_min_sentences || 3
        const chapters = st.story ? st.story.chapters : []
        let n = 0
        let current = false
        for (const c of chapters) {
            let count = c.sentence_count
            if (c.chapter_no === st.chapterNo) {
                current = true
                count = written().length
            }
            if (count >= min) n += 1
        }
        if (!current && written().length >= min) n += 1
        return n
    }
    function canFinish() {
        const need = st.rules ? st.rules.story_finish_min_chapters : null
        return dbMode && st.kind === 'fairy' && !!st.entry && !st.finished && !!need && storyQualified() >= need
    }
    // 나갈 때 물을지: 3·6·10장째를 채웠고 아직 '이어 쓸래요'를 안 고른 구간이면 그 구간, 마지막 장(100장)을 채웠으면 매번
    function finishPrompt() {
        if (!canFinish()) return null
        const rules = st.rules || {}
        const max = rules.story_max_chapters || 100
        if ((st.displayNo || st.chapterNo) >= max && written().length >= (rules.story_chapter_min_sentences || 3)) return { last: true }
        const asked = st.story ? st.story.finish_asked || 0 : 0
        const q = storyQualified()
        const due = (rules.story_finish_ask_at || []).filter((m) => q >= m && m > asked)
        return due.length ? { upto: Math.max(...due) } : null
    }
    // 나가기 전에 부른다. 물어봤으면 true (화면은 나가지 않고 기다린다)
    function askComplete() {
        if (st.busy || leaving) return false
        const p = finishPrompt()
        if (!p) return false
        track('finish_offer', { ...p, from: 'leave', chapter: st.chapterNo, qualified: storyQualified() })
        st.finishAsk = { ...p, from: 'leave' }
        st.finishError = ''
        emit()
        return true
    }
    // '이야기 끝내기' 버튼
    function openFinish() {
        if (!canFinish() || st.busy) return
        track('finish_offer', { from: 'button', chapter: st.chapterNo, qualified: storyQualified() })
        st.finishAsk = { from: 'button' }
        st.finishError = ''
        emit()
    }
    // how: later(다음에 이어 쓸래요) · stay(계속 쓸래요) · esc
    function closeComplete(how) {
        const ask = st.finishAsk
        if (!ask) return
        track('finish_offer_close', { how, upto: ask.upto || null, last: !!ask.last })
        if (how === 'later' && ask.upto) {
            if (st.story) st.story = { ...st.story, finish_asked: Math.max(st.story.finish_asked || 0, ask.upto) }
            api(`/api/books/${encodeURIComponent(book)}/finish-later`, { method: 'POST', body: { upto: ask.upto } })
                .catch((e) => { authFailed(e) })            // 못 적어도 다음에 한 번 더 물을 뿐이다
        }
        st.finishAsk = null
        st.finishError = ''
        emit()
    }
    async function completeNow() {
        if (st.finishSaving) return
        st.finishSaving = true
        st.finishError = ''
        emit()
        try {
            if (!(await retrySaves())) throw new Error('저장되지 않은 문장이 있어요.')
            await api(`/api/books/${encodeURIComponent(book)}/finish`, { method: 'POST' })
            track('story_finished', { entry: st.entry.id, chapter: st.chapterNo, qualified: storyQualified() })
            leaving = true
            onSaved(st.entry.id)
        } catch (e) {
            if (authFailed(e)) return
            st.finishError = `이야기를 끝내지 못했어요. 쓴 이야기는 그대로 있어요. (${e.message})`
            st.finishSaving = false
            track('story_finish_fail', { message: short(e) })
            emit()
        }
    }

    // ── 일기: 나가기 전에 '저장할까요?' ──
    // 하루치 기준(rules.diary_day_sentences)만큼 썼는데 아직 '이야기 저장하기'를 안 했으면(쓰는 중) 묻는다. 물어봤으면 true
    function askSave() {
        if (!dbMode || st.kind !== 'diary' || !st.entry || st.busy || leaving) return false
        if (st.entry.status === 'done') return false
        const need = st.rules ? st.rules.diary_day_sentences : 3
        if (written().length < need) return false
        track('save_offer', { entry: st.entry.id, sentences: written().length })
        st.saveAsk = true
        st.storyError = ''
        emit()
        return true
    }
    // how: stay(계속 쓸래요) · leave(저장하지 않고 나가기) · esc
    function closeSave(how) {
        if (!st.saveAsk) return
        track('save_offer_close', { how })
        st.saveAsk = false
        emit()
    }

    // 나가도 되는지: 쓰던 글자나 저장 안 된 문장이 있으면 화면이 한 번 물어본다
    function unsavedWork() {
        if (leaving) return null
        const typing = st.busy || (st.box.trim().length > 0 && !(dbMode && draftSafe()))   // 임시저장된 글자는 '쓰던 글자'로 치지 않는다
        const unsaved = dbMode ? st.sentences.some((x) => x.original && x.saveState !== 'saved') : written().length > 0
        if (!typing && !unsaved) return null
        return { typing, unsaved }
    }

    emit()
    return {
        subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn) },
        getSnapshot: () => snapshot,
        dispose() {
            if (draftTimer) syncDraft(true)                 // 기다리던 임시저장이 있으면 나가기 전에 보낸다
            clearTimeout(undoTimer)                         // 나가면 되돌리기는 사라진다
            draftWaitSince = null
            disposed = true
            if (exprResolve) exprResolve()
        },
        boot, submit, choose, setBox(v) { st.box = v; emit(); syncDraft(false) }, flushDraft,
        startEdit, cancelEdit, startInsert, moveSentence, retrySaves,
        askDelete, cancelDelete, confirmDelete, undoDelete,
        openTopics, chooseTopic, closeTopics, topicChangeable, pickExpr, confirmExpr, retryExpr, skipExpr,
        toggleFix(id, open) { const s = st.sentences.find((x) => x.id === id); if (s && !!s.openFix !== open) { s.openFix = open; emit() } },
        finish, backToWrite, restart, saveStory, unsavedWork,
        askComplete, openFinish, canFinish, closeComplete, completeNow, askSave, closeSave,
        chapterNav, askNext, closeNext,
        noteLeave(info) { track('leave_prompt', info) },
        noteDateChange(from, to) { track('date_change', { from, to }) },
    }
}
