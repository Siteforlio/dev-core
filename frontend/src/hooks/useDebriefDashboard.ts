import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { useOverlayStore } from '../store/overlayStore'
import { apiFetch } from '../lib/apiFetch'
import type {
  DebriefTab, ActionItem, AgendaItem, Attendee, Decision,
  CalendarDay, SelectedDate, MeetingDebrief,
} from '../types/debrief'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pad(n: number) { return String(n).padStart(2, '0') }

function todaySelected(): SelectedDate {
  const d = new Date()
  return { y: d.getFullYear(), m: d.getMonth(), d: d.getDate() }
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : (parts[0]?.[0] ?? '?').toUpperCase()
}

const AVATAR_COLORS = ['#0f766e', '#0891b2', '#22d3ee', '#0e7490', '#155e63', '#7c3aed', '#db2777']

function toAttendee(raw: { name: string; email: string }, idx: number): Attendee {
  return {
    name: raw.name || raw.email,
    email: raw.email,
    role: '',
    initials: initials(raw.name || raw.email),
    color: AVATAR_COLORS[idx % AVATAR_COLORS.length],
    status: 'present',
  }
}

function isLiveNow(dtstart_iso?: string, dtend_iso?: string, nowMs?: number): boolean {
  if (!dtstart_iso || !dtend_iso || !nowMs) return false
  return nowMs >= new Date(dtstart_iso + 'Z').getTime() &&
         nowMs <= new Date(dtend_iso   + 'Z').getTime()
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useDebriefDashboard(pendingSessionId: string | null = null) {
  const token = useAuthStore((s) => s.accessToken)
  const authHeaders = useRef<Record<string, string>>({})
  useEffect(() => { authHeaders.current = { Authorization: `Bearer ${token}` } }, [token])

  // ── Tick ──────────────────────────────────────────────────────────────────
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  // ── Calendar view ─────────────────────────────────────────────────────────
  const [viewYear,  setViewYear]  = useState(() => new Date().getFullYear())
  const [viewMonth, setViewMonth] = useState(() => new Date().getMonth())
  const [selected,  setSelected]  = useState<SelectedDate>(todaySelected)

  // ── Calendar data from API ────────────────────────────────────────────────
  const [calendarConfigured, setCalendarConfigured] = useState(false)
  const [caldavLoading,    setCaldavLoading]    = useState(false)
  const [eventsByDay,      setEventsByDay]      = useState<Record<number, AgendaItem[]>>({})
  const [eventDaySet,      setEventDaySet]      = useState<Set<number>>(new Set())
  const [selectedEvent,    setSelectedEvent]    = useState<AgendaItem | null>(null)

  const fetchCalendarMonth = useCallback(async (year: number, month: number) => {
    if (!token) return
    setCaldavLoading(true)
    const firstDay = new Date(year, month, 1)
    const lastDay  = new Date(year, month + 1, 0)
    const fmt = (d: Date) => d.toISOString().split('T')[0]
    try {
      const res = await apiFetch(
        `/api/v1/integrations/caldav/events?start=${fmt(firstDay)}&end=${fmt(lastDay)}`,
        { headers: authHeaders.current },
      )
      const { data } = await res.json()
      setCalendarConfigured(data.google_configured || data.microsoft_configured)
      if (!data.configured) return
      const byDay: Record<number, AgendaItem[]> = {}
      const days = new Set<number>()
      for (const ev of data.events as AgendaItem[]) {
        const d = parseInt((ev.date ?? '').split('-')[2] ?? '0', 10)
        if (!d) continue
        if (!byDay[d]) byDay[d] = []
        byDay[d].push(ev)
        days.add(d)
      }
      setEventsByDay(byDay)
      setEventDaySet(days)
    } catch { /* keep current state */ }
    finally { setCaldavLoading(false) }
  }, [token])

  // Fetch on mount + when month changes + poll every 60s
  useEffect(() => {
    fetchCalendarMonth(viewYear, viewMonth)
    const id = setInterval(() => fetchCalendarMonth(viewYear, viewMonth), 60_000)
    return () => clearInterval(id)
  }, [viewYear, viewMonth, fetchCalendarMonth])

  // ── Recent debriefs (for meeting picker when nothing is selected) ─────────
  const [recentDebriefs, setRecentDebriefs] = useState<MeetingDebrief[]>([])
  const [recentLoading,  setRecentLoading]  = useState(false)

  const fetchRecentDebriefs = useCallback(async () => {
    if (!token) return
    setRecentLoading(true)
    try {
      const res = await apiFetch('/api/v1/meeting-debriefs/recent?limit=30', { headers: authHeaders.current })
      if (!res.ok) return
      const { data } = await res.json()
      setRecentDebriefs(data ?? [])
    } catch { /* non-fatal */ }
    finally { setRecentLoading(false) }
  }, [token])

  useEffect(() => { fetchRecentDebriefs() }, [fetchRecentDebriefs])

  // Load a debrief directly from the picker without needing a CalDAV event
  const selectDebriefDirect = useCallback((d: MeetingDebrief) => {
    setDebrief(d)
    setNotesTextRaw(d.notes ?? '')
    setActionItems((d.actions ?? []) as ActionItem[])
    setDecisions((d.decisions ?? []) as Decision[])
    setMeetingStarted(false)
    setStartedAt(null)
  }, [])

  // ── Debrief state ─────────────────────────────────────────────────────────
  const [debrief,        setDebrief]        = useState<MeetingDebrief | null>(null)
  const [debriefLoading, setDebriefLoading] = useState(false)
  const [activeTab,      setActiveTab]      = useState<DebriefTab>('notes')
  const [notesText,      setNotesTextRaw]   = useState('')
  const [actionItems,    setActionItems]    = useState<ActionItem[]>([])
  const [decisions,      setDecisions]      = useState<Decision[]>([])
  const [meetingStarted, setMeetingStarted] = useState(false)
  const [startedAt,      setStartedAt]      = useState<number | null>(null)

  // Drive timer from actual WS state — only mark started when backend confirms session
  const wsState = useOverlayStore((s) => s.state)
  const prevWsState = useRef<string>('idle')
  useEffect(() => {
    const prev = prevWsState.current
    prevWsState.current = wsState

    const wasActive = prev !== 'idle' && prev !== 'paused'
    const isActive  = wsState !== 'idle' && wsState !== 'paused'

    if (!wasActive && isActive) {
      // Session just went active (listening/thinking) — start timer
      setMeetingStarted(true)
      setStartedAt(Date.now())
    } else if (wsState === 'paused' && !meetingStarted) {
      // Session paused before timer was ever set — mark started so timer is visible
      setMeetingStarted(true)
      if (!startedAt) setStartedAt(Date.now())
    } else if (wsState === 'idle' && prev !== 'idle') {
      // Session fully ended — clear timer and refresh debriefs
      setMeetingStarted(false)
      setStartedAt(null)
      // Small delay so backend has time to write the session summary
      setTimeout(() => fetchRecentDebriefs(), 3000)
    }
  }, [wsState, meetingStarted, startedAt])

  // Refs so callbacks always see latest state without stale closures
  const debriefRef     = useRef<MeetingDebrief | null>(null)
  const actionItemsRef = useRef<ActionItem[]>([])
  const decisionsRef   = useRef<Decision[]>([])
  useEffect(() => { debriefRef.current     = debrief      }, [debrief])
  useEffect(() => { actionItemsRef.current = actionItems  }, [actionItems])
  useEffect(() => { decisionsRef.current   = decisions    }, [decisions])

  const fetchOrCreateDebrief = useCallback(async (event: AgendaItem) => {
    if (!token) return
    setDebriefLoading(true)
    setNotesTextRaw('')
    setActionItems([])
    setDecisions([])
    setDebrief(null)
    try {
      const res = await apiFetch('/api/v1/meeting-debriefs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders.current },
        body: JSON.stringify({
          calendar_event_uid: event.uid || null,
          date: event.date || null,
          title: event.title,
          location: event.location || null,
          start_time: event.time || null,
          duration_minutes: event.duration_minutes || null,
          attendees: (event.attendees ?? []).map((a, i) => ({
            name: a.name,
            email: a.email,
            role: '',
            initials: initials(a.name || a.email),
            color: AVATAR_COLORS[i % AVATAR_COLORS.length],
            status: 'present',
          })),
        }),
      })
      const { data } = await res.json()
      setDebrief(data)
      setNotesTextRaw(data.notes ?? '')
      setActionItems(data.actions ?? [])
      setDecisions(data.decisions ?? [])
    } catch { /* keep clean state on error */ }
    finally { setDebriefLoading(false) }
  }, [token])

  const selectEvent = useCallback((event: AgendaItem) => {
    setSelectedEvent(event)
    setMeetingStarted(false)
    setStartedAt(null)
    fetchOrCreateDebrief(event)
  }, [fetchOrCreateDebrief])

  // ── Link Cluely session when Dashboard fires onSessionStarted ─────────────
  useEffect(() => {
    if (!pendingSessionId || !debriefRef.current) return
    const id = debriefRef.current.id
    apiFetch(`/api/v1/meeting-debriefs/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders.current },
      body: JSON.stringify({ cluely_session_id: pendingSessionId }),
    })
      .then(r => r.json())
      .then(({ data }) => { if (data) setDebrief(data) })
      .catch(() => {})
  }, [pendingSessionId])

  // ── Toast ─────────────────────────────────────────────────────────────────
  const [toastVisible, setToastVisible] = useState(false)
  const [toastMsg,     setToastMsg]     = useState('')
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current) }, [])

  const showToast = useCallback((msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    setToastVisible(true)
    setToastMsg(msg)
    toastTimerRef.current = setTimeout(() => setToastVisible(false), 3400)
  }, [])

  // ── Notes — debounced PATCH (1s) ──────────────────────────────────────────
  const notesSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (notesSaveTimer.current) clearTimeout(notesSaveTimer.current) }, [])

  const setNotesText = useCallback((text: string) => {
    setNotesTextRaw(text)
    if (!debriefRef.current) return
    if (notesSaveTimer.current) clearTimeout(notesSaveTimer.current)
    notesSaveTimer.current = setTimeout(async () => {
      try {
        const res = await apiFetch(`/api/v1/meeting-debriefs/${debriefRef.current!.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders.current },
          body: JSON.stringify({ notes: text }),
        })
        const { data } = await res.json()
        setDebrief(data)
      } catch { /* silently fail — user keeps typing */ }
    }, 1000)
  }, [])

  // ── Action items — immediate PATCH ───────────────────────────────────────
  const toggleActionItem = useCallback(async (i: number) => {
    setActionItems(prev => {
      const updated = prev.map((it, idx) => idx === i ? { ...it, done: !it.done } : it)
      if (debriefRef.current) {
        apiFetch(`/api/v1/meeting-debriefs/${debriefRef.current.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders.current },
          body: JSON.stringify({ actions: updated }),
        }).then(r => r.json()).then(({ data }) => setDebrief(data)).catch(() => {})
      }
      return updated
    })
  }, [])

  // startMeeting is now driven by WS state (see wsState effect above)

  // ── Month navigation ──────────────────────────────────────────────────────
  const changeMonth = useCallback((delta: number) => {
    let nm = viewMonth + delta
    let ny = viewYear
    if (nm < 0)  { nm = 11; ny -= 1 }
    if (nm > 11) { nm = 0;  ny += 1 }
    setViewMonth(nm)
    setViewYear(ny)
  }, [viewMonth, viewYear])

  // ── Email ─────────────────────────────────────────────────────────────────
  const [modalOpen,    setModalOpen]    = useState(false)
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody,    setEmailBody]    = useState('')
  const [emailTo,      setEmailTo]      = useState('')
  const [sendingEmail, setSendingEmail] = useState(false)

  const [composingEmail, setComposingEmail] = useState(false)

  const openEmail = useCallback(async (meetingTitle: string) => {
    const attends = (debriefRef.current?.attendees ?? []) as Attendee[]
    const addrs   = attends.filter(a => a.email).map(a => a.email as string).join(', ')
    // Open modal immediately — AI will fill subject + body
    setEmailSubject('')
    setEmailBody('')
    setEmailTo(addrs)
    setComposingEmail(true)
    setModalOpen(true)

    if (!debriefRef.current) {
      setComposingEmail(false)
      return
    }
    try {
      const res = await apiFetch(
        `/api/v1/meeting-debriefs/${debriefRef.current.id}/compose-email`,
        { method: 'POST', headers: authHeaders.current },
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const { data } = await res.json()
      setEmailSubject(data.subject ?? `${meetingTitle} — Follow-up`)
      setEmailBody(data.body ?? '')
    } catch {
      // Fallback to a minimal template so the user can still edit and send
      setEmailBody(`Hi,\n\nFollowing up on our ${meetingTitle} session.\n\nPlease let me know if you have any questions.\n\nBest,`)
    } finally {
      setComposingEmail(false)
    }
  }, [])

  const closeEmail = useCallback(() => setModalOpen(false), [])

  const sendEmail = useCallback(async () => {
    const addresses = emailTo.split(',').map(s => s.trim()).filter(Boolean)
    if (!addresses.length) { showToast('Enter at least one recipient email address'); return }
    setSendingEmail(true)
    try {
      const res = await apiFetch('/api/v1/integrations/email/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders.current },
        body: JSON.stringify({ to: addresses, subject: emailSubject, body: emailBody }),
      })
      if (!res.ok) {
        const b = await res.json().catch(() => null)
        showToast(`Failed to send: ${b?.detail ?? `HTTP ${res.status}`}`)
        return
      }
      setModalOpen(false)
      showToast(`Follow-up sent to ${addresses.length} recipient${addresses.length > 1 ? 's' : ''}`)
    } catch { showToast('Network error — check your connection') }
    finally  { setSendingEmail(false) }
  }, [emailTo, emailSubject, emailBody, showToast])

  // ── AI summary ────────────────────────────────────────────────────────────
  const generateSummary = useCallback(async () => {
    if (!debriefRef.current) return
    showToast('Generating AI summary…')
    try {
      const res = await apiFetch(`/api/v1/meeting-debriefs/${debriefRef.current.id}/summarize`, {
        method: 'POST',
        headers: authHeaders.current,
      })
      const { data } = await res.json()
      setDebrief(data)
      // Reload extracted actions/decisions from the AI response
      if (data.actions?.length)   setActionItems(data.actions)
      if (data.decisions?.length) setDecisions(data.decisions)
      showToast('AI summary ready')
    } catch { showToast('Summary generation failed') }
  }, [showToast])

  // Auto-generate when a debrief with a linked session loads (status = none)
  useEffect(() => {
    if (!debrief?.cluely_session_id) return
    if (debrief.ai_summary_status !== 'none') return
    generateSummary()
  }, [debrief?.id, debrief?.ai_summary_status])

  // ── Derived: countdown from real event start time ─────────────────────────
  let countdownText: string
  let countdownLabel: string
  let heroKicker: string

  if (meetingStarted && startedAt !== null) {
    const el = Math.max(0, now - startedAt)
    countdownText  = `${pad(Math.floor(el/3600000))}:${pad(Math.floor((el%3600000)/60000))}:${pad(Math.floor((el%60000)/1000))}`
    countdownLabel = 'Elapsed'
    heroKicker     = 'In progress'
  } else if (selectedEvent?.dtstart_iso) {
    const startMs   = new Date(selectedEvent.dtstart_iso + 'Z').getTime()
    const currentlyLive = isLiveNow(selectedEvent.dtstart_iso, selectedEvent.dtend_iso, now)
    if (currentlyLive) {
      const el = Math.max(0, now - startMs)
      countdownText  = `${pad(Math.floor(el/3600000))}:${pad(Math.floor((el%3600000)/60000))}:${pad(Math.floor((el%60000)/1000))}`
      countdownLabel = 'Elapsed'
      heroKicker     = 'In progress'
    } else {
      const rem = Math.max(0, startMs - now)
      countdownText  = `${pad(Math.floor(rem/3600000))}:${pad(Math.floor((rem%3600000)/60000))}:${pad(Math.floor((rem%60000)/1000))}`
      countdownLabel = rem === 0 ? 'Ready' : 'Starts in'
      heroKicker     = rem === 0 ? 'Starting now' : 'Up next'
    }
  } else {
    countdownText  = '—'
    countdownLabel = 'Select a meeting'
    heroKicker     = 'No meeting selected'
  }

  // ── Derived: calendar grid ────────────────────────────────────────────────
  const monthLabel = new Date(viewYear, viewMonth, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' })
  const firstDow   = new Date(viewYear, viewMonth, 1).getDay()
  const dim        = new Date(viewYear, viewMonth + 1, 0).getDate()
  const prevDim    = new Date(viewYear, viewMonth, 0).getDate()
  const realToday  = todaySelected()

  // Days in this view month that have a DB debrief record
  const debriefDaySet = new Set<number>(
    recentDebriefs
      .filter(d => {
        if (!d.date) return false
        const [y, m] = d.date.split('-').map(Number)
        return y === viewYear && m - 1 === viewMonth
      })
      .map(d => parseInt(d.date!.split('-')[2], 10))
  )

  const calendarDays: CalendarDay[] = Array.from({ length: 42 }, (_, i) => {
    const dayNum     = i - firstDow + 1
    const inMonth    = dayNum >= 1 && dayNum <= dim
    const label      = inMonth ? dayNum : (dayNum < 1 ? prevDim + dayNum : dayNum - dim)
    const isToday    = inMonth && viewYear === realToday.y && viewMonth === realToday.m && dayNum === realToday.d
    const isSelected = inMonth && selected.y === viewYear && selected.m === viewMonth && selected.d === dayNum
    const hasEvent   = inMonth && (eventDaySet.has(dayNum) || debriefDaySet.has(dayNum))
    return {
      label, inMonth, isToday, isSelected, hasEvent,
      onClick: inMonth ? () => {
        setSelected({ y: viewYear, m: viewMonth, d: dayNum })
        // Clear active debrief so Follow-up card resets to the new date's meetings
        setDebrief(null)
        setNotesTextRaw('')
        setActionItems([])
        setDecisions([])
        setSelectedEvent(null)
        setMeetingStarted(false)
        setStartedAt(null)
      } : () => {},
    }
  })

  // ── Derived: agenda with per-second live badge ────────────────────────────
  const rawAgenda: AgendaItem[] = eventsByDay[selected.d] ?? []
  const agenda: AgendaItem[] = rawAgenda.map(ev => ({
    ...ev,
    live: isLiveNow(ev.dtstart_iso, ev.dtend_iso, now),
  }))

  const selectedLabel = new Date(selected.y, selected.m, selected.d)
    .toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })

  // ── Derived: debriefs for the selected date (drives Follow-up picker) ─────
  const selDateStr = `${selected.y}-${pad(selected.m + 1)}-${pad(selected.d)}`
  const selectedDateDebriefs = recentDebriefs.filter(d => d.date === selDateStr)

  // ── Derived: attendees ────────────────────────────────────────────────────
  const liveAttendees: Attendee[] =
    debrief?.attendees?.length      ? (debrief.attendees as Attendee[])          :
    selectedEvent?.attendees?.length ? selectedEvent.attendees.map(toAttendee)   :
    []

  // ── Derived: stats ────────────────────────────────────────────────────────
  const doneCount     = actionItems.filter(a => a.done).length
  const totalCount    = actionItems.length
  const completionPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0
  const isCurrentlyLive = isLiveNow(selectedEvent?.dtstart_iso, selectedEvent?.dtend_iso, now)
  const statusLabel   = meetingStarted || isCurrentlyLive ? 'Live now' : selectedEvent ? 'Up next' : 'No meeting'

  return {
    now,
    viewYear, viewMonth, selected,
    activeTab, setActiveTab,
    meetingStarted, notesText, setNotesText,
    actionItems, toggleActionItem,
    decisions,
    modalOpen, emailSubject, setEmailSubject, emailBody, setEmailBody,
    emailTo, setEmailTo, sendingEmail, composingEmail,
    toastVisible, toastMsg,
    calendarConfigured, caldavLoading,
    debrief, debriefLoading,
    recentDebriefs, recentLoading, selectDebriefDirect, selectedDateDebriefs,
    selectedEvent, selectEvent,
    changeMonth, openEmail, closeEmail, sendEmail, generateSummary,
    monthLabel, calendarDays, selectedLabel, agenda,
    countdownText, countdownLabel, heroKicker,
    doneCount, totalCount, completionPct, statusLabel,
    attendees: liveAttendees,
  }
}
