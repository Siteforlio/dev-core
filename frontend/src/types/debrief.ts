export type DebriefTab = 'notes' | 'summary' | 'actions' | 'decisions' | 'people'

export interface ActionItem {
  text: string
  owner: string
  due: string
  done: boolean
}

export interface AgendaItem {
  uid?: string
  time: string
  dur?: string
  title: string
  tag: string
  color: string
  live: boolean
  location?: string
  dtstart_iso?: string   // "YYYY-MM-DDTHH:MM:SS" UTC — used for live badge recalc
  dtend_iso?: string
  duration_minutes?: number
  attendees?: { name: string; email: string }[]
  date?: string          // "YYYY-MM-DD"
}

export interface MeetingDebrief {
  id: string
  calendar_event_uid: string | null
  date: string | null
  title: string
  location: string | null
  start_time: string | null
  duration_minutes: number | null
  notes: string | null
  actions: ActionItem[]
  decisions: Decision[]
  attendees: Attendee[]
  ai_summary: string | null
  ai_summary_status: 'none' | 'pending' | 'done' | 'error'
  updated_at: string
}

export interface Attendee {
  name: string
  role: string
  initials: string
  color: string
  status: 'present' | 'away'
  email?: string
}

export interface Decision {
  text: string
  meta: string
}

export interface CalendarDay {
  label: number
  inMonth: boolean
  isToday: boolean
  isSelected: boolean
  hasEvent: boolean
  onClick: () => void
}

export interface SelectedDate {
  y: number
  m: number
  d: number
}

export interface DebriefState {
  now: number
  viewYear: number
  viewMonth: number
  selected: SelectedDate
  activeTab: DebriefTab
  meetingStarted: boolean
  startedAt: number | null
  notesText: string
  actionItems: ActionItem[]
  modalOpen: boolean
  emailSubject: string
  emailBody: string
  toastVisible: boolean
  toastMsg: string
}
