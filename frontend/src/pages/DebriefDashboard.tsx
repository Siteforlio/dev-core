import { useDebriefDashboard } from '../hooks/useDebriefDashboard'
import DebriefCalendarPanel  from '../components/devcore/debrief/DebriefCalendarPanel'
import DebriefHeroPanel      from '../components/devcore/debrief/DebriefHeroPanel'
import DebriefNotesPanel     from '../components/devcore/debrief/DebriefNotesPanel'
import DebriefFollowUpPanel  from '../components/devcore/debrief/DebriefFollowUpPanel'
import DebriefEmailModal     from '../components/devcore/debrief/DebriefEmailModal'
import DebriefToast          from '../components/devcore/debrief/DebriefToast'

const ACCENT = '#22d3ee'

interface Props {
  onStartSession: () => void
  pendingSessionId?: string | null
}

export default function DebriefDashboard({ onStartSession, pendingSessionId }: Props) {
  const {
    now,
    activeTab, setActiveTab,
    meetingStarted,
    notesText, setNotesText,
    actionItems, toggleActionItem,
    decisions,
    modalOpen, emailSubject, setEmailSubject, emailBody, setEmailBody,
    emailTo, setEmailTo, sendingEmail, composingEmail,
    toastVisible, toastMsg,
    changeMonth, openEmail, closeEmail, sendEmail, generateSummary,
    monthLabel, calendarDays, selectedLabel, agenda,
    countdownText, countdownLabel, heroKicker,
    doneCount, totalCount, completionPct, statusLabel,
    attendees, calendarConfigured, caldavLoading,
    selectedEvent, selectEvent,
    debrief, debriefLoading,
    recentDebriefs, recentLoading, selectDebriefDirect, selectedDateDebriefs,
  } = useDebriefDashboard(pendingSessionId ?? null)

  // ── Live badge: recalculated every second from the now tick ──────────────
  const isLive = selectedEvent
    ? (selectedEvent.dtstart_iso && selectedEvent.dtend_iso
        ? now >= new Date(selectedEvent.dtstart_iso + 'Z').getTime() &&
          now <= new Date(selectedEvent.dtend_iso + 'Z').getTime()
        : selectedEvent.live)
    : meetingStarted

  // ── Hero data: from selected event or defaults ────────────────────────────
  const meetingTitle = selectedEvent?.title ?? debrief?.title ?? 'Select a meeting'
  const heroTime     = selectedEvent?.time   ?? '—'
  const heroRoom     = selectedEvent?.location ?? selectedEvent?.tag ?? '—'

  // ── AI summary ────────────────────────────────────────────────────────────
  const aiSummary   = debrief?.ai_summary ?? null
  const aiStatus    = debrief?.ai_summary_status ?? 'none'

  const aiHighlights = [
    { label: 'Decisions',    value: String(decisions.length) },
    { label: 'Open actions', value: String(actionItems.filter(a => !a.done).length) },
  ]

  const stats = [
    { label: 'Decisions',    value: String(decisions.length) },
    { label: 'Actions done', value: `${doneCount}/${totalCount}` },
    { label: 'Attendees',    value: String(attendees.length) },
  ]

  // Current date label (realtime from now)
  const dateLabel = new Date(now).toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  })

  return (
    <div style={{
      minHeight: '100%',
      background: '#070f1c',
      color: '#e2e8f0',
      fontFamily: "'Manrope', system-ui, sans-serif",
      padding: '24px',
    }}>
      {/* Status bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '20px',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: '22px', letterSpacing: '-0.02em', color: '#f1f5f9' }}>
            {meetingTitle}
          </div>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '7px',
            padding: '4px 12px',
            borderRadius: '999px',
            background: isLive ? 'rgba(239,68,68,0.12)' : 'rgba(34,211,238,0.1)',
            border: `1px solid ${isLive ? 'rgba(239,68,68,0.3)' : 'rgba(34,211,238,0.25)'}`,
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            color: isLive ? '#f87171' : '#22d3ee',
          }}>
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: isLive ? '#ef4444' : '#22d3ee',
              animation: 'dcPulse 2s ease-in-out infinite',
              flexShrink: 0,
            }} />
            {isLive ? 'Live now' : statusLabel}
          </span>
          {(debriefLoading || caldavLoading) && (
            <div style={{ width: '14px', height: '14px', border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          )}
          {!calendarConfigured && !caldavLoading && (
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'rgba(251,146,60,0.8)', fontFamily: 'monospace' }}>
              Calendar not connected — go to Settings
            </span>
          )}
        </div>
        <div style={{ fontSize: '13px', fontWeight: 500, color: 'rgba(148,163,184,0.6)', fontFamily: 'monospace' }}>
          {dateLabel}
        </div>
      </div>

      {/* 3-column grid */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-start' }}>

        {/* LEFT — Calendar + Agenda */}
        <DebriefCalendarPanel
          monthLabel={monthLabel}
          calendarDays={calendarDays}
          selectedLabel={selectedLabel}
          agenda={agenda}
          accent={ACCENT}
          onPrevMonth={() => changeMonth(-1)}
          onNextMonth={() => changeMonth(1)}
          onSelectEvent={selectEvent}
          selectedEventUid={selectedEvent?.uid}
        />

        {/* CENTER — Hero + Notes */}
        <div style={{ flex: '2 1 440px', minWidth: '320px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <DebriefHeroPanel
            heroKicker={heroKicker}
            meetingTitle={meetingTitle}
            heroTime={heroTime}
            heroRoom={heroRoom}
            heroAttendees={attendees.length}
            countdownLabel={countdownLabel}
            countdownText={countdownText}
            meetingStarted={meetingStarted}
            onStartSession={onStartSession}
            isLive={isLive}
          />
          <DebriefNotesPanel
            activeTab={activeTab}
            onTabChange={setActiveTab}
            notesText={notesText}
            onNotesChange={setNotesText}
            aiSummary={aiSummary}
            aiConfidence={aiStatus === 'done' ? 'High' : aiStatus === 'pending' ? 'Generating…' : null}
            aiHighlights={aiHighlights}
            actionItems={actionItems}
            onToggleAction={toggleActionItem}
            decisions={decisions}
            attendees={attendees}
          />
        </div>

        {/* RIGHT — Follow-up + Stats */}
        <DebriefFollowUpPanel
          onOpenEmail={() => openEmail(meetingTitle)}
          stats={stats}
          completionPct={completionPct}
          doneCount={doneCount}
          totalCount={totalCount}
          hasMeeting={debrief !== null}
          meetingTitle={meetingTitle}
          recentDebriefs={selectedDateDebriefs.length > 0 ? selectedDateDebriefs : recentDebriefs}
          recentLoading={recentLoading}
          onSelectDebrief={selectDebriefDirect}
        />
      </div>

      <DebriefEmailModal
        open={modalOpen}
        recipients={attendees.map(a => ({ name: a.name }))}
        toEmails={emailTo}
        onToEmailsChange={setEmailTo}
        subject={emailSubject}
        body={emailBody}
        onSubjectChange={setEmailSubject}
        onBodyChange={setEmailBody}
        onClose={closeEmail}
        onSend={sendEmail}
        sending={sendingEmail}
        composing={composingEmail}
      />
      <DebriefToast visible={toastVisible} message={toastMsg} />
    </div>
  )
}
