// 글쓰기 화면의 두뇌. 화면(WritePage.jsx)은 여기의 상태를 그리기만 하고, 버튼을 누르면 여기의 함수를 부른다.
// frontend/temp/index.html 에 있던 동작을 그대로 옮겼다.
//
//   한 문장의 흐름:  submit() → /validate → (통과) /correct 스트림 → 문장 저장 → (동화) 표현 추천
//   저장은 한 번에 하나씩 차례로 한다 (saveChain). 문장 순서가 뒤바뀌지 않게 하기 위해서다.
//   문장의 저장 번호(seq)는 따로 갖지 않는다. 목록에서의 위치 + 1 이 그 번호다.
//
//   쓰던 문장 임시저장: 아직 통과하지 않은 입력칸의 글자를 서버(글의 draft 칸)에 덮어써 둔다 (syncDraft).
//     · 입력을 멈추고 DRAFT_DELAY_MS 가 지나면   · '확인하기'를 누르면 바로   · 이 화면에서 나갈 때
//     다시 들어오면 boot() 가 입력칸에 되살린다 (다시쓰기 · 위에 넣기 중이었다면 그 상태까지).
//     문장이 저장되면 서버가 임시저장을 비운다.
//
// 쓰는 법:  const w = createWriter({ book, date, practice, onSaved, onAuthError, onDateChange })
//          w.subscribe(fn) / w.getSnapshot()  → 화면이 상태를 읽는다 (useSyncExternalStore)
//          w.boot()                          → 화면이 열릴 때 한 번
import { api, apiStream, track as trackEvent } from './api.js'

const DRAFT_DELAY_MS = 2000 // 입력을 멈추고 이만큼(1000 = 1초) 지나면 쓰던 문장을 임시저장한다

const track = (event, data) => trackEvent(event, data, 'write')
const short = (e) => String((e && e.message) || e).slice(0, 200)
const day10 = (v) => (v ? String(v).slice(0, 10) : null)

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
        topic: '',                // 동화: 고른 주제
        topicBox: null,           // 동화: 주제 추천 { pick, others }
        expr: null,               // 동화: 표현 추천 { status: 'loading'|'ready'|'error', base, options, value }
        view: 'write',            // write / all(전체 글)
        storySaving: false,
        storyError: '',
        focusTick: 0,             // 바뀔 때마다 화면이 입력칸에 커서를 둔다
        scrollTo: null,           // { id, tick } 그 줄이 보이게 스크롤
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
    let exprResolve = null
    let leaving = false         // 저장하고 다른 화면으로 넘어가는 중
    let disposed = false
    let bootRun = 0             // boot 를 부른 횟수 (늦게 끝난 이전 boot 의 결과를 버리는 데 쓴다)
    let tick = 0
    let draftSent = ''          // 서버에 임시저장되어 있는 내용 (draftKey 모양). 비어 있으면 임시저장 없음
    let draftTimer = null       // 입력이 멈추기를 기다리는 타이머

    function emit() {
        if (disposed) return
        snapshot = { ...st, sentences: st.sentences.map((s) => ({ ...s, work: s.work ? { ...s.work } : undefined })), save: { ...st.save } }
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
            if (r.changed) draftSent = ''                   // 문장이 저장되면 서버가 임시저장을 비운다
            st.entry.status = r.entry.status
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

    // 서버의 임시저장을 지금 상태에 맞춘다. now 가 아니면 입력이 멈추기를 기다렸다가 한다.
    // 문장 저장과 같은 줄(saveChain)에 세워서, 문장 저장 → 임시저장 순서가 뒤바뀌지 않게 한다.
    // fixed 를 주면 '지금 상태' 대신 그 내용을 저장한다 (확인하기를 누른 순간의 글자: 차례가 올 때쯤엔 입력칸이 비어 있을 수 있다).
    function syncDraft(now, fixed = null) {
        if (!dbMode || !st.entry || disposed) return
        clearTimeout(draftTimer)
        draftTimer = null
        if (!now) { draftTimer = setTimeout(() => syncDraft(true), DRAFT_DELAY_MS); return }
        saveChain = saveChain.then(async () => {
            if (leaving) return                             // '이야기 저장하기'로 넘어가는 중이면 건드리지 않는다
            if (!fixed && st.busy && !st.box.trim()) return // 교정 중: 입력칸은 비었지만 그 문장은 아직 저장 전이다 → 임시저장을 남겨 둔다
            const d = fixed || draftNow()
            // 저장하지 못한 문장이 있으면 임시저장을 지우지 않는다 (그 문장의 마지막 보관본일 수 있다)
            if (!d.text && st.sentences.some((x) => x.original && x.saveState !== 'saved')) return
            const key = draftKey(d)
            if (key === draftSent) return
            try {
                await api(`/api/entries/${st.entry.id}/draft`, { method: 'PUT', body: d })
                draftSent = key
                emit()                                        // 나가기 전 안내(unsavedWork)가 바뀔 수 있다
            } catch (e) {
                authFailed(e)                                 // 임시저장 실패는 따로 알리지 않는다 (나갈 때 '저장되지 않은 글'로 물어본다)
            }
        })
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
        id: nextId++, original: x.original, revised: x.revised, retry_count: Math.max(0, (x.attempt_count || 1) - 1),
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

    // ── 동화 주제 (고른 주제는 이 브라우저에만 기억한다) ──
    const topicKey = () => `fairy-topic-${book}`
    function loadTopic() { try { return localStorage.getItem(topicKey()) || '' } catch { return '' } }
    function storeTopic(v) { try { if (v) localStorage.setItem(topicKey(), v); else localStorage.removeItem(topicKey()) } catch { /* 무시 */ } }

    async function openTopics(more) {
        if (!more) shownTopics = []
        let r
        try {
            r = await api(`/topics?exclude=${encodeURIComponent(shownTopics.join(','))}`)
        } catch {
            return                                          // 추천을 못 받아도 글쓰기는 그대로 할 수 있다
        }
        shownTopics = shownTopics.concat([r.pick], r.others)
        track(more ? 'topic_more' : 'topic_open', { pick: r.pick, others: r.others })
        st.topicBox = { pick: r.pick, others: r.others }
        emit()
    }

    function chooseTopic(v) {
        st.topic = v || ''
        storeTopic(st.topic)
        track(v ? 'topic_pick' : 'topic_skip', v ? { topic: v, shown: shownTopics.length } : { shown: shownTopics.length })
        st.topicBox = null
        focus()
        emit()
        loadQuestion()
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
            const r = await api(`/api/books/${encodeURIComponent(book)}/entries`, { method: 'POST', body: date ? { date } : {} })
            if (disposed || run !== bootRun) return
            st.entry = { id: r.entry.id, date: day10(r.entry.date), status: r.entry.status }
            st.bookTitle = r.book.title
            st.kind = r.book.kind === 'fairy' ? 'fairy' : 'diary'
            st.sentences = r.sentences.map(fromServer)
            st.loading = false
            st.busy = false
            restoreDraft(r.entry)
            if (st.kind === 'fairy') {                      // 동화: 아직 한 줄도 안 썼고 주제도 없으면 주제부터 추천한다
                st.topic = loadTopic()
                if (!st.topic && !st.sentences.length) openTopics(false)
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
        if (st.busy) return
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
        if (st.busy) return
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
        if (st.busy) return
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
    function offerExpressions(s) {
        return new Promise((resolve) => {
            const base = s.revised || s.original
            exprResolve = () => { st.expr = null; exprResolve = null; resolve() }
            const load = async () => {
                st.expr = { status: 'loading', base, options: [], value: 'keep', sentenceId: s.id, load }
                emit()
                let r
                try {
                    r = await api('/suggest', { method: 'POST', body: { sentence: base } })
                } catch (e) {
                    track('expr_fail', { message: short(e) })
                    st.expr = { ...st.expr, status: 'error' }
                    emit()
                    return
                }
                const options = (r.options || []).filter((o) => typeof o === 'string' && o && o !== base).slice(0, 3)
                track('expr_shown', { options: options.length })
                if (!options.length) { exprResolve(); emit(); return }
                st.expr = { ...st.expr, status: 'ready', options }
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
        const picked = e.value !== 'keep' ? e.options[Number(e.value)] : null
        track('expr_pick', { picked: picked ? Number(e.value) : null, options: e.options.length })
        if (s) {
            s.expression_choice = { base: e.base, options: e.options, picked }   // 무엇을 보여 줬고 무엇을 골랐는지 (DB의 expression_choice)
            if (picked) s.revised = picked
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
        if (st.busy) return
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
            disposed = true
            if (exprResolve) exprResolve()
        },
        boot, submit, choose, setBox(v) { st.box = v; emit(); syncDraft(false) },
        startEdit, cancelEdit, startInsert, moveSentence, retrySaves,
        openTopics, chooseTopic, pickExpr, confirmExpr, retryExpr, skipExpr,
        toggleFix(id, open) { const s = st.sentences.find((x) => x.id === id); if (s && !!s.openFix !== open) { s.openFix = open; emit() } },
        finish, backToWrite, restart, saveStory, unsavedWork,
        noteLeave(info) { track('leave_prompt', info) },
        noteDateChange(from, to) { track('date_change', { from, to }) },
    }
}
