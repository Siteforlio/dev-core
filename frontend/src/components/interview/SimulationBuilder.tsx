import { useState, useEffect, useRef, useCallback } from 'react'
import './SimulationBuilder.css'
import { useSimulationStore } from '../../store/simulationStore'
import { apiFetch } from '../../lib/apiFetch'
import { pickCharacter } from './InterviewerCharacters'

// ============================================================
// TYPES
// ============================================================

interface Attachment {
  kind: 'file' | 'path' | 'image' | 'snippet'
  name: string
  meta?: string
}

interface Field {
  k: string
  v: string
  accent?: boolean
}

interface UnderstoodState {
  confident: boolean
  summaryParts: (string | { hl: string })[]
  fields: Field[]
}

interface Preset {
  id: string
  title: string
  desc: string
  icon: string
  seed: string
}

interface Signal {
  tag: string
  vi: boolean
}

interface Refinement {
  label: string
  apply: (u: UnderstoodState) => UnderstoodState
  reply: string
}

interface BrainStats {
  nodes: number
  active: number
  edges: number
  pulses: number
}

// Brain engine types
interface BrainNode {
  bx: number; by: number; x: number; y: number
  th: number; rad: number; ph: number; sp: number; amp: number; lit: number
}
interface BrainEdge { a: number; b: number; len: number }
interface BrainPulse { ei: number; t: number; sp: number; dir: 1 | -1; vi: boolean }
interface BrainBurst { r: number; max: number; born: number }
interface BrainEngine {
  w: number; h: number; cx: number; cy: number; R: number
  nodes: BrainNode[]; edges: BrainEdge[]; adj: number[][]
  pulses: BrainPulse[]; bursts: BrainBurst[]
  t: number; flash: number
}

export interface SimSessionParams {
  text: string
  attachments: Attachment[]
  understood: UnderstoodState | null
}

interface Props {
  onLaunch?: (params: SimSessionParams) => void
}

interface ChatMsg {
  id: string
  who: 'user' | 'ai'
  text: string
  card?: UnderstoodState
}

// ============================================================
// DATA & LOGIC
// ============================================================

const PRESETS: Preset[] = [
  { id: 'pitch', title: '90-Second Pitch', desc: 'Investor elevator pitch, hard time cap', icon: 'bolt', seed: "I have 90 seconds to pitch my startup to an investor. Cut me off at exactly 90 seconds, then grill me on the weakest part of the pitch." },
  { id: 'mr', title: 'MR Review + Live Pairing', desc: 'Review a merge request, then pair live', icon: 'merge', seed: "GitLab-style interview. They gave me a merge request to review out loud, then I work live with a developer to ship a fix. Play the developer — collaborative but you have opinions." },
  { id: 'sysdesign', title: 'System Design', desc: 'Whiteboard a scalable system', icon: 'graph', seed: "45-minute system design interview. Ask me to design a scalable system and play a senior engineer who keeps probing tradeoffs, bottlenecks, and failure modes." },
  { id: 'behavioral', title: 'Behavioral Panel', desc: 'STAR questions from a hiring panel', icon: 'people', seed: "Behavioral interview with a two-person panel. Ask me about conflict, a failure, and a leadership moment. Push for specifics and don't let me stay vague." },
  { id: 'demo', title: 'Project Demo', desc: 'Present & defend a project to stakeholders', icon: 'present', seed: "I present my project to a room of stakeholders, then defend the technical and product decisions under scrutiny. Mix of supportive and skeptical voices." },
  { id: 'blank', title: 'Blank Canvas', desc: 'Start from a clean prompt', icon: 'spark', seed: '' },
]

const SIGNAL_RULES: { re: RegExp; tag: string; vi?: boolean }[] = [
  { re: /\b(pitch|elevator|investor|vc|fundrais|seed round)\b/i, tag: 'pitch' },
  { re: /\b(merge request|\bmr\b|pull request|\bpr\b|diff|code review|review)\b/i, tag: 'code-review' },
  { re: /\b(pair|pairing|live cod|work live|together)\b/i, tag: 'live-pairing' },
  { re: /\b(system design|architecture|scalab|throughput|latency|distributed)\b/i, tag: 'system-design' },
  { re: /\b(behavioral|star method|conflict|leadership|failure|teamwork)\b/i, tag: 'behavioral' },
  { re: /\b(gitlab|stripe|google|amazon|meta|netflix|openai|anthropic)\b/i, tag: 'named-company', vi: true },
  { re: /\b(demo|present|presentation|stakeholder|showcase)\b/i, tag: 'demo' },
  { re: /\b(\d+)\s*(sec|second|min|minute|hour)/i, tag: 'time-boxed', vi: true },
  { re: /\b(skeptic|tough|grill|hostile|push back|hard questions|aggressive)\b/i, tag: 'high-pressure', vi: true },
  { re: /\b(senior|staff|principal|cto|vp|director)\b/i, tag: 'senior-level' },
  { re: /\b(junior|entry|intern|new grad)\b/i, tag: 'junior-level' },
  { re: /\b(take[- ]?home|assignment|challenge)\b/i, tag: 'take-home' },
  { re: /\b(sales|negotiat|deal|close|objection)\b/i, tag: 'sales' },
  { re: /\b(panel|two|three|multiple interviewers|board)\b/i, tag: 'panel' },
  { re: /\b(role[- ]?play|simulate|scenario|practice|rehears)\b/i, tag: 'roleplay' },
]

function detectSignals(text: string, attachments: Attachment[]): Signal[] {
  const found: Signal[] = []
  const seen = new Set<string>()
  for (const r of SIGNAL_RULES) {
    if (r.re.test(text) && !seen.has(r.tag)) {
      seen.add(r.tag)
      found.push({ tag: r.tag, vi: !!r.vi })
    }
  }
  attachments.forEach((a) => {
    const t = a.kind === 'image' ? 'image-attached' : a.kind === 'path' ? 'path-linked' : 'file-attached'
    if (!seen.has(t)) { seen.add(t); found.push({ tag: t, vi: a.kind === 'path' }) }
  })
  return found
}

function contextLevel(text: string, attachments: Attachment[], hasPreset: boolean): number {
  const words = (text.trim().match(/\S+/g) || []).length
  let s = 0
  s += Math.min(words / 55, 0.62)
  s += attachments.length * 0.11
  s += hasPreset ? 0.14 : 0
  const signals = detectSignals(text, attachments).length
  s += Math.min(signals * 0.05, 0.25)
  return Math.max(0, Math.min(1, s))
}

function pick(text: string, map: [RegExp, string][], fallback: string): string {
  for (const [re, val] of map) if (re.test(text)) return val
  return fallback
}

function getField(u: UnderstoodState, k: string): string {
  const f = u.fields.find((x) => x.k === k)
  return f ? f.v : ''
}
function setField(u: UnderstoodState, k: string, v: string): UnderstoodState {
  return { ...u, fields: u.fields.map((f) => (f.k === k ? { ...f, v } : f)) }
}
function halveTime(t: string): string {
  const m = t.match(/(\d+)/)
  if (!m) return '60 seconds — hard cap'
  const n = Math.max(1, Math.round(parseInt(m[1], 10) / 2))
  return t.replace(/\d+/, String(n))
}
function cap(s: string): string {
  s = (s || '').trim()
  return s ? s[0].toUpperCase() + s.slice(1) : s
}

function interpret(text: string, attachments: Attachment[], presetId: string | null): UnderstoodState {
  const t = (text || '').toLowerCase()
  const atts = attachments || []

  let time = 'Open-ended'
  const tm = t.match(/(\d+)\s*(sec|second|min|minute|hour)/)
  if (tm) {
    const n = tm[1]; const u = tm[2]
    time = u.startsWith('sec') ? `${n} seconds — hard cap` : u.startsWith('min') ? `${n} minutes` : `${n} hour${n === '1' ? '' : 's'}`
  } else if (/pitch|elevator/.test(t)) time = '~90 seconds'
  else if (/system design|architecture/.test(t)) time = '~45 minutes'

  const format = pick(t, [
    [/merge request|\bmr\b|code review|review.*(then|and).*pair/, 'MR review → live pairing'],
    [/pair|live cod|work live/, 'Live pair-programming'],
    [/system design|architecture/, 'Whiteboard system design'],
    [/pitch|elevator/, 'Timed verbal pitch + Q&A'],
    [/behavioral|star/, 'Behavioral Q&A'],
    [/demo|present|showcase/, 'Presentation + defense'],
    [/take[- ]?home/, 'Take-home walkthrough'],
    [/sales|negotiat/, 'Negotiation roleplay'],
  ], 'Conversational interview')

  const iPlay = pick(t, [
    [/gitlab|developer|engineer|pair/, 'Senior developer + interviewer'],
    [/investor|vc|fundrais/, 'Skeptical investor'],
    [/stakeholder|product|pm/, 'Mixed stakeholder room'],
    [/recruiter|hr|behavioral/, 'Hiring manager'],
    [/panel|board/, 'Interview panel (2–3 voices)'],
    [/sales|client|customer/, 'Prospective client'],
    [/cto|vp|director|principal|staff/, 'Senior leadership'],
  ], 'Your counterpart')

  const youPlay = pick(t, [
    [/pitch|present|demo|founder|startup/, 'Presenter / founder'],
    [/candidate|interview|hire/, 'Candidate'],
    [/sales|negotiat/, 'The seller'],
  ], 'You — as yourself')

  const tone = pick(t, [
    [/skeptic|tough|grill|hostile|aggressive|hard questions|push back/, 'High pressure — pointed, probing'],
    [/friendly|supportive|warm|gentle|easy/, 'Supportive — encouraging'],
    [/junior|entry|new grad/, 'Calibrated for early-career'],
  ], 'Realistic — professional but testing')

  let materials = 'None attached'
  if (atts.length) {
    materials = atts.map((a) => a.name).join(' · ')
  } else if (/diff|merge request|\bmr\b/.test(t)) {
    materials = 'Expecting a diff / MR — attach it for realism'
  }

  const focus = pick(t, [
    [/merge request|code review|pair|diff/, 'Code reasoning, tradeoff articulation, communication under review'],
    [/system design|architecture/, 'Scoping, tradeoffs, bottlenecks, failure modes'],
    [/pitch|investor/, 'Clarity, the hook, defensibility, the weakest claim'],
    [/behavioral|star/, 'Specificity, ownership, measurable outcomes'],
    [/demo|present/, 'Narrative, decision justification, handling tough questions'],
  ], 'Structure, clarity, and how you hold up when pressed')

  let scenario = text.trim()
  if (scenario.length > 180) scenario = scenario.slice(0, 177).trim() + '…'
  if (!scenario) scenario = "a custom rehearsal you haven't described yet"

  const confident = (text.trim().match(/\S+/g) || []).length >= 6 || atts.length > 0 || !!presetId

  const summaryParts: (string | { hl: string })[] = [
    'You want to rehearse ',
    { hl: format.toLowerCase() },
    '. I\'ll run it as ',
    { hl: iPlay.toLowerCase() },
    `${time !== 'Open-ended' ? `, held to ${time.toLowerCase()}` : ''}.`,
  ]

  return {
    confident,
    summaryParts,
    fields: [
      { k: 'Scenario', v: scenario },
      { k: 'You play', v: youPlay },
      { k: "I'll play", v: iPlay, accent: true },
      { k: 'Format', v: format },
      { k: 'Time', v: time },
      { k: 'Materials', v: materials },
      { k: 'Pressure', v: tone },
      { k: "I'll push on", v: focus },
    ],
  }
}

const REFINEMENTS: Refinement[] = [
  { label: 'Make them tougher', apply: (u) => setField(u, 'Pressure', 'Aggressive — relentless, interrupts, finds the cracks'), reply: 'Cranking up the heat. Expect interruptions and pointed follow-ups.' },
  { label: 'Go easier on me', apply: (u) => setField(u, 'Pressure', 'Supportive — encouraging, coaches between answers'), reply: "Softened. I'll guide more and let you recover from stumbles." },
  { label: 'Cut the time in half', apply: (u) => setField(u, 'Time', halveTime(getField(u, 'Time'))), reply: "Tighter clock. You'll feel the time pressure sooner." },
  { label: 'Add a curveball', apply: (u) => setField(u, "I'll push on", getField(u, "I'll push on") + ' + one unexpected curveball'), reply: "Added a wildcard — something you won't see coming, mid-session." },
  { label: 'Make them more senior', apply: (u) => setField(u, "I'll play", 'Staff/Principal-level — deep, exacting'), reply: 'Raised the bar. Your counterpart now operates at staff+ depth.' },
  { label: 'Panel of three', apply: (u) => setField(u, "I'll play", 'Panel of three — different angles each'), reply: 'Now a three-person panel. Voices will trade off and disagree.' },
]

function applyFreeRefine(u: UnderstoodState, text: string): { u: UnderstoodState; reply: string } {
  const raw = (text || '').trim()
  if (!raw) return { u, reply: '' }
  const lc = raw.toLowerCase()
  let nu = u
  const changes: string[] = []

  function afterLast(re: RegExp): string | null {
    const ms = [...lc.matchAll(re)]
    if (!ms.length) return null
    const m = ms[ms.length - 1]
    let s = raw.slice(m.index! + m[0].length)
    s = s.replace(/^[\s:,\-–—]+/, '').replace(/^(a|an|the)\s+/i, '').replace(/[.,;!]+$/, '').trim()
    return s
  }

  const persona = afterLast(/\b(?:you are|you're|you will be|you'll be|you should be|you play|act as|pretend to be|roleplay as)\b/g)
  if (persona && !/^not\b/i.test(persona) && persona.length > 1) {
    nu = setField(nu, "I'll play", cap(persona))
    changes.push("I'll play → " + cap(persona))
  }

  const mine = afterLast(/\b(?:i am|i'm|i play|i will be|i'll be|i should be|my role is|make me)\b/g)
  if (mine && !/^not\b/i.test(mine) && mine.length > 1) {
    nu = setField(nu, 'You play', cap(mine))
    changes.push('You play → ' + cap(mine))
  }

  const tm = lc.match(/(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)/)
  if (tm) {
    const n = tm[1], unit = tm[2]
    const v = /^sec/.test(unit) ? `${n} seconds — hard cap` : /^min/.test(unit) ? `${n} minutes` : `${n} hour${n === '1' ? '' : 's'}`
    nu = setField(nu, 'Time', v); changes.push('Time → ' + v)
  } else if (/\b(shorter|less time|cut the time|cut time|faster|speed it up|quicker)\b/.test(lc)) {
    const v = halveTime(getField(nu, 'Time')); nu = setField(nu, 'Time', v); changes.push('Time → ' + v)
  }

  if (/\b(tough|tougher|harder|aggressive|brutal|grill|relentless|hostile|skeptical|ruthless|hard on me)\b/.test(lc)) {
    nu = setField(nu, 'Pressure', 'High pressure — pointed, interrupts, probing'); changes.push('Pressure → high')
  } else if (/\b(easier|go easy|gentle|friendly|supportive|nicer|calm|kind|relax|chill)\b/.test(lc)) {
    nu = setField(nu, 'Pressure', 'Supportive — encouraging, coaches between answers'); changes.push('Pressure → supportive')
  }

  const fm = lc.match(/\b(?:focus on|ask about|push on|test my|dig into|grill me on|hammer on|probe(?:\s+my)?)\s+(.+)/)
  if (fm) {
    const idx = lc.indexOf(fm[1])
    const f = cap(raw.slice(idx).replace(/[.,;!]+$/, '').trim())
    nu = setField(nu, "I'll push on", f); changes.push("I'll push on → " + f)
  }

  if (changes.length) {
    return { u: nu, reply: 'Updated — ' + changes.join('  ·  ') + '.' }
  }

  const hasNotes = nu.fields.some((f) => f.k === 'Adjustments')
  const fields = hasNotes
    ? nu.fields.map((f) => f.k === 'Adjustments' ? { ...f, v: f.v + ' · ' + raw } : f)
    : [...nu.fields, { k: 'Adjustments', v: raw, accent: true }]
  return { u: { ...nu, fields }, reply: 'Got it — folded that into the brief.' }
}

// ============================================================
// ICON
// ============================================================

function Icon({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  const s: React.CSSProperties = { width: size, height: size, fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round', display: 'block', flexShrink: 0 }
  const paths: Record<string, React.ReactNode> = {
    bolt:   <path d="M13 2 4 13h6l-1 9 9-12h-6z" />,
    merge:  <g><circle cx="6" cy="5" r="2.2"/><circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="12" r="2.2"/><path d="M6 7v6a4 4 0 0 0 4 4h6M6 17v-2"/></g>,
    graph:  <g><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M6.5 7.5 10.5 16M17.5 7.5 13.5 16M7 6h10"/></g>,
    people: <g><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5.8M21 20a6 6 0 0 0-4-5.6"/></g>,
    present:<g><rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M12 16v4M8 20h8M8 8l3 3 4-5"/></g>,
    spark:  <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />,
    file:   <g><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></g>,
    path:   <g><path d="M4 7h7l2 2h7"/><path d="M4 7v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9"/></g>,
    image:  <g><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="m4 17 5-4 4 3 3-2 4 3"/></g>,
    snippet:<g><path d="M8 7 4 12l4 5M16 7l4 5-4 5M13 5l-2 14"/></g>,
    brain:  <g><path d="M9 3a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 1 5 3 3 0 0 0 4 3V3zM15 3a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-1 5 3 3 0 0 1-4 3V3z"/></g>,
    arrow:  <path d="M5 12h14M13 6l6 6-6 6" />,
    play:   <g><circle cx="12" cy="12" r="9"/><path d="M10 8.5 16 12l-6 3.5z" fill="currentColor" stroke="none"/></g>,
    send:   <path d="m4 12 16-8-6 16-3-7z" />,
    plus:   <path d="M12 5v14M5 12h14" />,
    check:  <path d="M4 12l5 5L20 6" />,
    edit:   <path d="M14 4l6 6M3 21l4-1L20 7l-3-3L4 17z" />,
    refresh:<path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 4v4h-4M21 12a9 9 0 0 1-15 6.7L3 16M3 20v-4h4" />,
    x:      <path d="M6 6l12 12M18 6 6 18" />,
  }
  return <svg viewBox="0 0 24 24" style={s} className={className}>{paths[name]}</svg>
}

// ============================================================
// BRAIN VIZ  (untouched)
// ============================================================

function hexToRgb(h: string): [number, number, number] {
  h = h.replace('#', '')
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  const n = parseInt(h, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
function lerp(a: number, b: number, t: number) { return a + (b - a) * t }
function mixRgb(a: [number,number,number], b: [number,number,number], t: number): [number,number,number] {
  return [lerp(a[0],b[0],t), lerp(a[1],b[1],t), lerp(a[2],b[2],t)]
}
function rgba(c: [number,number,number], a: number) { return `rgba(${c[0]|0},${c[1]|0},${c[2]|0},${a})` }

function brainPath(ctx: CanvasRenderingContext2D, cx: number, cy: number, R: number) {
  const steps = 220
  ctx.beginPath()
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2
    let r = 1 + 0.085*Math.sin(3*a+0.4) + 0.05*Math.sin(6*a+1.1) + 0.032*Math.sin(9*a+2.3) + 0.02*Math.sin(13*a)
    const top = Math.exp(-Math.pow((a-(Math.PI*1.5)),2)/0.05)
    const bot = Math.exp(-Math.pow((a-(Math.PI*0.5)),2)/0.05)
    r -= 0.16*top + 0.13*bot
    const x = cx + Math.cos(a)*R*r*1.12
    const y = cy + Math.sin(a)*R*r*0.86
    if (i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y)
  }
  ctx.closePath()
}

function buildEngine(w: number, h: number): BrainEngine {
  const cx = w*0.5, cy = h*0.5
  const R = Math.min(w,h)*0.34
  const mc = document.createElement('canvas')
  mc.width = w; mc.height = h
  const mx = mc.getContext('2d')!
  mx.fillStyle = '#fff'
  brainPath(mx, cx, cy, R)
  mx.fill()
  const mask = mx.getImageData(0,0,w,h).data
  const inside = (x: number, y: number) => {
    x = x|0; y = y|0
    if (x<0||y<0||x>=w||y>=h) return false
    return mask[(y*w+x)*4+3] > 128
  }
  const target = Math.min(210, Math.max(110, Math.round((R*R)/240)))
  const minD = R*0.085
  const cell = minD
  const grid = new Map<string, number[]>()
  const key = (gx: number, gy: number) => gx+','+gy
  const nodes: BrainNode[] = []
  let tries = 0
  while (nodes.length < target && tries < target*60) {
    tries++
    const a = Math.random()*Math.PI*2
    const rr = Math.pow(Math.random(), 0.62)
    const x = cx + Math.cos(a)*rr*R*1.12
    const y = cy + Math.sin(a)*rr*R*0.86
    if (!inside(x,y)) continue
    const gx = (x/cell)|0, gy = (y/cell)|0
    let ok = true
    for (let ox=-1; ox<=1&&ok; ox++)
      for (let oy=-1; oy<=1&&ok; oy++) {
        const arr = grid.get(key(gx+ox,gy+oy))
        if (arr) for (const j of arr) {
          const dx = nodes[j].bx-x, dy = nodes[j].by-y
          if (dx*dx+dy*dy < minD*minD) ok = false
        }
      }
    if (!ok) continue
    const d = Math.hypot((x-cx)/1.12, (y-cy)/0.86)/R
    nodes.push({ bx:x, by:y, x, y, th:Math.min(0.97, Math.pow(d,0.85)*0.92+Math.random()*0.08), rad:lerp(2.4,1.3,d)+Math.random()*0.5, ph:Math.random()*Math.PI*2, sp:0.4+Math.random()*0.7, amp:lerp(1.4,3.2,d), lit:0 })
    const k = key(gx,gy)
    if (!grid.has(k)) grid.set(k,[])
    grid.get(k)!.push(nodes.length-1)
  }
  const edges: BrainEdge[] = []
  const maxD = minD*2.5
  for (let i=0; i<nodes.length; i++) {
    const cand: [number,number][] = []
    for (let j=0; j<nodes.length; j++) {
      if (i===j) continue
      const dx=nodes[i].bx-nodes[j].bx, dy=nodes[i].by-nodes[j].by
      const dd=dx*dx+dy*dy
      if (dd < maxD*maxD) cand.push([dd,j])
    }
    cand.sort((a,b)=>a[0]-b[0])
    const kk = Math.min(3, cand.length)
    for (let c=0; c<kk; c++) {
      const j=cand[c][1]
      if (i<j) edges.push({a:i,b:j,len:Math.sqrt(cand[c][0])})
      else if (!edges.some(e=>e.a===j&&e.b===i)) edges.push({a:j,b:i,len:Math.sqrt(cand[c][0])})
    }
  }
  const adj = nodes.map(()=>[] as number[])
  edges.forEach((e,ei)=>{ adj[e.a].push(ei); adj[e.b].push(ei) })
  return { w, h, cx, cy, R, nodes, edges, adj, pulses:[], bursts:[], t:0, flash:0 }
}

function BrainViz({ level=0, burst=0, cyan='#5ad6ee', violet='#9b7bff', intensity=1, onStats }: {
  level?: number; burst?: number; cyan?: string; violet?: string; intensity?: number
  onStats?: (s: BrainStats) => void
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const engineRef = useRef<BrainEngine|null>(null)
  const rafRef = useRef(0)
  const levelRef = useRef(level)
  const intenRef = useRef(intensity)
  const colRef = useRef({ cy: hexToRgb(cyan), vi: hexToRgb(violet) })
  const lastBurst = useRef(burst)
  const statTick = useRef(0)

  useEffect(() => { levelRef.current = level }, [level])
  useEffect(() => { intenRef.current = intensity }, [intensity])
  useEffect(() => { colRef.current = { cy: hexToRgb(cyan), vi: hexToRgb(violet) } }, [cyan, violet])

  useEffect(() => {
    if (burst !== lastBurst.current) {
      lastBurst.current = burst
      const e = engineRef.current
      if (e) { e.bursts.push({ r: e.R*0.15, max: e.R*1.9, born: e.t }); e.flash = 1 }
    }
  }, [burst])

  useEffect(() => {
    const host = hostRef.current!
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    let dpr = Math.min(window.devicePixelRatio||1, 2)
    let smoothLevel = 0

    function resize() {
      const w = host.clientWidth, h = host.clientHeight
      if (w<4||h<4) return
      dpr = Math.min(window.devicePixelRatio||1, 2)
      canvas.width = w*dpr; canvas.height = h*dpr
      canvas.style.width = w+'px'; canvas.style.height = h+'px'
      engineRef.current = buildEngine(w, h)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(host)
    resize()
    const kicks = [60,250,600,1200,2500].map((d)=>setTimeout(resize,d))
    window.addEventListener('load', resize)

    function frame() {
      try {
        if (!engineRef.current && host.clientWidth>4 && host.clientHeight>4) resize()
        const e = engineRef.current
        if (e && e.nodes.length===0 && host.clientWidth>4 && host.clientHeight>4) {
          engineRef.current = buildEngine(host.clientWidth, host.clientHeight)
        }
        if (e) {
          const w=e.w, h=e.h
          ctx.setTransform(dpr,0,0,dpr,0,0)
          ctx.clearRect(0,0,w,h)
          e.t += 1/60
          const tgt = levelRef.current
          smoothLevel += (tgt-smoothLevel)*0.06
          const L = smoothLevel
          const I = intenRef.current
          const C = colRef.current
          e.flash *= 0.92

          const breathe = 1+0.014*Math.sin(e.t*0.9)+L*0.015
          const swayX = Math.sin(e.t*0.5)*5
          const swayY = Math.cos(e.t*0.37)*4

          ctx.save()
          ctx.translate(e.cx+swayX, e.cy+swayY)
          ctx.scale(breathe, breathe)
          ctx.translate(-e.cx, -e.cy)

          ctx.globalCompositeOperation = 'lighter'
          const haloA = (0.05+L*0.22+e.flash*0.25)*I
          const halo = ctx.createRadialGradient(e.cx,e.cy,e.R*0.2,e.cx,e.cy,e.R*1.7)
          const hc = mixRgb(C.cy, C.vi, L*0.5)
          halo.addColorStop(0, rgba(hc, haloA))
          halo.addColorStop(0.5, rgba(hc, haloA*0.4))
          halo.addColorStop(1, rgba(hc, 0))
          ctx.fillStyle = halo
          ctx.fillRect(e.cx-e.R*1.8, e.cy-e.R*1.8, e.R*3.6, e.R*3.6)

          for (const n of e.nodes) {
            const want = L>=n.th ? 1 : (L>n.th-0.12 ? (L-(n.th-0.12))/0.12 : 0)
            n.lit += (want-n.lit)*0.07
            n.x = n.bx + Math.cos(e.t*n.sp+n.ph)*n.amp
            n.y = n.by + Math.sin(e.t*n.sp*0.8+n.ph)*n.amp
          }

          ctx.lineWidth = 1
          for (const ed of e.edges) {
            const A=e.nodes[ed.a], B=e.nodes[ed.b]
            const lit = Math.min(A.lit, B.lit)
            const base = 0.04+0.015*Math.sin(e.t*0.6+ed.len)
            const a = (base+lit*0.32)*I
            if (a<0.015) continue
            const col = mixRgb(C.cy, C.vi, lit*L*0.55)
            ctx.strokeStyle = rgba(col, a)
            ctx.beginPath(); ctx.moveTo(A.x,A.y); ctx.lineTo(B.x,B.y); ctx.stroke()
          }

          ctx.strokeStyle = rgba(C.cy, 0.05*I)
          ctx.lineWidth = 1.5
          ctx.beginPath()
          ctx.moveTo(e.cx, e.cy-e.R*0.78)
          ctx.bezierCurveTo(e.cx-e.R*0.06, e.cy-e.R*0.2, e.cx+e.R*0.05, e.cy+e.R*0.2, e.cx, e.cy+e.R*0.78)
          ctx.stroke()

          for (const n of e.nodes) {
            const lit = n.lit
            const col = mixRgb(C.cy, C.vi, lit*L*0.6)
            const tw = 0.6+0.4*Math.sin(e.t*2.4+n.ph)
            const glowR = n.rad*(2.4+lit*4)*(1+e.flash*0.6)
            const ga = (0.04+lit*0.5*(0.7+0.3*tw))*I
            if (ga>0.02) {
              const g = ctx.createRadialGradient(n.x,n.y,0,n.x,n.y,glowR)
              g.addColorStop(0, rgba(col, ga)); g.addColorStop(1, rgba(col, 0))
              ctx.fillStyle = g
              ctx.beginPath(); ctx.arc(n.x,n.y,glowR,0,Math.PI*2); ctx.fill()
            }
            ctx.fillStyle = rgba(lit>0.5 ? [235,252,255] : col as [number,number,number], (0.25+lit*0.75)*I)
            ctx.beginPath(); ctx.arc(n.x,n.y,n.rad*(0.7+lit*0.5),0,Math.PI*2); ctx.fill()
          }

          const litEdges = e.edges.filter(ed=>Math.min(e.nodes[ed.a].lit,e.nodes[ed.b].lit)>0.4)
          const wantPulses = Math.round((litEdges.length*0.05+L*14)*I)+(e.flash>0.3?18:0)
          while (e.pulses.length<wantPulses && litEdges.length) {
            const ed = litEdges[(Math.random()*litEdges.length)|0]
            e.pulses.push({ ei:e.edges.indexOf(ed), t:Math.random(), sp:(0.6+Math.random()*0.9)/Math.max(ed.len,1), dir:Math.random()<0.5?1:-1, vi:Math.random()<L*0.5 })
          }
          for (let i=e.pulses.length-1; i>=0; i--) {
            const p = e.pulses[i]
            const ed = e.edges[p.ei]
            if (!ed) { e.pulses.splice(i,1); continue }
            p.t += p.sp*p.dir*(1+e.flash*1.5)
            if (p.t>1||p.t<0) {
              const endNode = p.t>1 ? ed.b : ed.a
              const opts = e.adj[endNode].filter(x=>x!==p.ei&&Math.min(e.nodes[e.edges[x].a].lit,e.nodes[e.edges[x].b].lit)>0.4)
              if (opts.length && Math.random()<0.55 && e.pulses.length<wantPulses+10) {
                const ne = opts[(Math.random()*opts.length)|0]
                const nd = e.edges[ne]
                p.ei=ne; p.dir=nd.a===endNode?1:-1; p.t=p.dir===1?0:1; p.sp=(0.6+Math.random()*0.9)/Math.max(nd.len,1)
              } else { e.pulses.splice(i,1); continue }
            }
            const A=e.nodes[ed.a], B=e.nodes[ed.b]
            const x=lerp(A.x,B.x,p.t), y=lerp(A.y,B.y,p.t)
            const col: [number,number,number] = p.vi ? C.vi : [200,248,255]
            const pr = 2.6+e.flash*2
            const g = ctx.createRadialGradient(x,y,0,x,y,pr*3)
            g.addColorStop(0, rgba(col,0.9*I)); g.addColorStop(1, rgba(col,0))
            ctx.fillStyle=g; ctx.beginPath(); ctx.arc(x,y,pr*3,0,Math.PI*2); ctx.fill()
            ctx.fillStyle=rgba([240,253,255],0.95*I)
            ctx.beginPath(); ctx.arc(x,y,pr*0.5,0,Math.PI*2); ctx.fill()
          }

          for (let i=e.bursts.length-1; i>=0; i--) {
            const b=e.bursts[i]
            b.r += (b.max-b.r)*0.06+2
            const prog = b.r/b.max
            if (prog>=1) { e.bursts.splice(i,1); continue }
            const a=(1-prog)*0.5*I
            ctx.strokeStyle=rgba(mixRgb(C.cy,C.vi,prog),a)
            ctx.lineWidth=2*(1-prog)+0.5
            ctx.beginPath(); ctx.arc(e.cx,e.cy,b.r,0,Math.PI*2); ctx.stroke()
          }

          ctx.restore()
          ctx.globalCompositeOperation = 'source-over'

          if (onStats && (statTick.current++%18===0)) {
            let active=0; for (const n of e.nodes) if (n.lit>0.5) active++
            onStats({ nodes:e.nodes.length, active, edges:e.edges.length, pulses:e.pulses.length })
          }
        }
      } catch(_) { /* keep loop alive */ }
      rafRef.current = requestAnimationFrame(frame)
    }
    rafRef.current = requestAnimationFrame(frame)
    return () => { cancelAnimationFrame(rafRef.current); ro.disconnect(); kicks.forEach(clearTimeout); window.removeEventListener('load', resize) }
  }, [])

  return (
    <div className="brain-canvas-host" ref={hostRef}>
      <canvas ref={canvasRef}></canvas>
    </div>
  )
}

// ============================================================
// LAUNCH OVERLAY
// ============================================================

function LaunchOverlay({ u, onClose, onConfirm }: { u: UnderstoodState|null; onClose: ()=>void; onConfirm: ()=>void }) {
  const [prog, setProg] = useState(0)
  const lines = ['allocating neural context…','loading materials & persona…','calibrating pressure model…','opening live channel…']
  const [step, setStep] = useState(0)

  useEffect(() => {
    let p = 0
    const id = setInterval(() => {
      p += 2+Math.random()*5
      setProg(Math.min(100,p))
      setStep(Math.min(lines.length-1, Math.floor((p/100)*lines.length)))
      if (p>=100) clearInterval(id)
    }, 90)
    return () => clearInterval(id)
  }, [])

  const ready = prog>=100
  const scenario = u ? (u.fields.find(f=>f.k==='Scenario')||{v:''}).v : ''
  const format = u ? (u.fields.find(f=>f.k==='Format')||{v:''}).v : ''

  return (
    <div className="launch-overlay">
      <div style={{width:'min(560px, 90vw)', border:'1px solid var(--line-2)', borderRadius:'var(--r-lg)', background:'var(--panel)', overflow:'hidden', boxShadow:'0 40px 120px -40px rgba(155,123,255,0.5)'}}>
        <div style={{padding:'22px 24px', borderBottom:'1px solid var(--line)'}}>
          <div className="eyebrow" style={{color:'var(--vi)'}}>{ready ? 'Channel open' : 'Initializing'}</div>
          <div style={{fontSize:19, fontWeight:700, marginTop:8, color:'var(--ink)', fontFamily:'var(--mono)'}}>{format||'Simulation'}</div>
          <div style={{fontSize:12.5, color:'var(--ink-dim)', marginTop:6, lineHeight:1.55, fontFamily:'var(--mono)'}}>{scenario}</div>
        </div>
        <div style={{padding:'20px 24px'}}>
          <div className="gauge-track" style={{height:5}}><div className="gauge-fill" style={{width:prog+'%'}}></div></div>
          <div style={{marginTop:14, display:'flex', flexDirection:'column', gap:7}}>
            {lines.map((l,i) => (
              <div key={i} style={{fontSize:11.5, letterSpacing:0.02, color:i<=step?'var(--cy)':'var(--ink-ghost)', display:'flex', gap:9, transition:'color 0.3s', fontFamily:'var(--mono)'}}>
                <span>{i<step||ready?'✓':i===step?'›':'·'}</span>{l}
              </div>
            ))}
          </div>
        </div>
        <div style={{padding:'16px 24px', borderTop:'1px solid var(--line)', display:'flex', gap:10, justifyContent:'flex-end'}}>
          <button className="sim-btn btn-ghost" onClick={onClose}>↩ Back</button>
          <button className="sim-btn btn-launch" disabled={!ready} onClick={onConfirm}>
            <Icon name="play" size={15} /> {ready ? 'Enter session' : 'Booting…'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// CHAT COMPONENTS
// ============================================================

function ContextCard({ u, onChip }: { u: UnderstoodState; onChip: (r: Refinement) => void }) {
  return (
    <div style={{ marginTop: 12 }}>
      {/* summary sentence */}
      <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', lineHeight: 1.6, marginBottom: 10 }}>
        {u.summaryParts.map((p, i) =>
          typeof p === 'string'
            ? <span key={i}>{p}</span>
            : <span key={i} style={{ color: 'var(--cy)', fontWeight: 600 }}>{(p as {hl:string}).hl}</span>
        )}
      </div>
      {/* compact fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0, border: '1px solid rgba(34,211,238,0.1)', borderRadius: 6, overflow: 'hidden' }}>
        {u.fields.map((f, i) => (
          <div key={f.k} style={{
            display: 'flex', gap: 10, padding: '6px 12px',
            background: i % 2 === 0 ? 'rgba(255,255,255,0.015)' : 'transparent',
            borderBottom: i < u.fields.length - 1 ? '1px solid rgba(34,211,238,0.06)' : 'none',
          }}>
            <span style={{ color: 'var(--ink-ghost)', fontSize: 11, width: 80, flexShrink: 0, letterSpacing: '0.05em', paddingTop: 1 }}>{f.k}</span>
            <span style={{ color: f.accent ? 'var(--vi)' : 'var(--cy)', fontSize: 12, lineHeight: 1.5 }}>{f.v}</span>
          </div>
        ))}
      </div>
      {/* quick chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
        {REFINEMENTS.map(r => (
          <button key={r.label} onClick={() => onChip(r)} style={{
            padding: '4px 10px',
            background: 'rgba(155,123,255,0.07)',
            border: '1px solid rgba(155,123,255,0.18)',
            borderRadius: 20,
            color: 'var(--vi)',
            fontSize: 11,
            cursor: 'pointer',
            fontFamily: 'var(--mono)',
            letterSpacing: '0.03em',
            transition: 'all 0.14s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(155,123,255,0.14)'; e.currentTarget.style.borderColor = 'rgba(155,123,255,0.4)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(155,123,255,0.07)'; e.currentTarget.style.borderColor = 'rgba(155,123,255,0.18)' }}
          >{r.label}</button>
        ))}
      </div>
    </div>
  )
}

function ChatBubble({ msg, onChip }: { msg: ChatMsg; onChip: (r: Refinement) => void }) {
  const isUser = msg.who === 'user'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{
        maxWidth: isUser ? '78%' : '94%',
        padding: '10px 14px',
        borderRadius: isUser ? '12px 4px 12px 12px' : '4px 12px 12px 12px',
        background: isUser
          ? 'linear-gradient(135deg, rgba(90,214,238,0.12), rgba(90,214,238,0.06))'
          : 'rgba(155,123,255,0.06)',
        border: isUser
          ? '1px solid rgba(90,214,238,0.22)'
          : '1px solid rgba(155,123,255,0.14)',
        fontSize: 13.5,
        lineHeight: 1.6,
        color: 'var(--ink)',
        fontFamily: 'var(--mono)',
      }}>
        {msg.text && <span>{msg.text}</span>}
        {msg.card && <ContextCard u={msg.card} onChip={onChip} />}
      </div>
    </div>
  )
}

function ThinkingBubble() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
      <div style={{
        padding: '12px 18px',
        borderRadius: '4px 12px 12px 12px',
        background: 'rgba(155,123,255,0.06)',
        border: '1px solid rgba(155,123,255,0.14)',
      }}>
        <span className="think-dots"><i></i><i></i><i></i></span>
      </div>
    </div>
  )
}

// ============================================================
// MAIN COMPONENT
// ============================================================

function stateWord(phase: string, level: number): string {
  if (phase==='interpreting') return 'synthesizing'
  if (phase==='understood') return 'ready'
  if (level<0.04) return 'dormant'
  if (level<0.35) return 'listening'
  if (level<0.7) return 'absorbing'
  return 'primed'
}

export default function SimulationBuilder({ onLaunch }: Props) {
  const setSession = useSimulationStore((s) => s.setSession)

  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [presetId, setPresetId] = useState<string|null>(null)
  const [phase, setPhase] = useState<'build'|'interpreting'|'understood'>('build')
  const [u, setU] = useState<UnderstoodState|null>(null)
  const [burst, setBurst] = useState(0)
  const [stats, setStats] = useState<BrainStats>({ nodes:0, active:0, edges:0, pulses:0 })
  const [showLaunch, setShowLaunch] = useState(false)
  const [launching, setLaunching] = useState(false)

  // Chat state
  const [messages, setMessages] = useState<ChatMsg[]>([{
    id: 'init',
    who: 'ai',
    text: "What do you want to rehearse? Describe the scenario, who you'll be speaking with, and how much pressure. Drop in files, paths, or snippets if you have materials.",
  }])
  const [chatInput, setChatInput] = useState('')
  const [inlineMode, setInlineMode] = useState<'path'|'snippet'|null>(null)
  const [inlineVal, setInlineVal] = useState('')

  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const inlineRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const imgRef = useRef<HTMLInputElement>(null)

  const fire = () => setBurst(b => b + 1)

  const base = contextLevel(text, attachments, !!presetId)
  const level = phase==='interpreting' ? Math.max(base,0.82) : phase==='understood' ? Math.min(1,base+0.3) : base
  const signals = detectSignals(text, attachments)
  const word = stateWord(phase, level)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, phase])

  useEffect(() => {
    if (inlineMode && inlineRef.current) inlineRef.current.focus()
  }, [inlineMode])

  const addAttachment = (a: Attachment) => { setAttachments(prev => [...prev, a]); fire() }
  const removeAttachment = (i: number) => setAttachments(prev => prev.filter((_, x) => x !== i))

  const humanSize = (b: number) => {
    if (!b && b !== 0) return ''
    if (b < 1024) return b + ' B'
    if (b < 1024*1024) return (b/1024).toFixed(0) + ' KB'
    return (b/1024/1024).toFixed(1) + ' MB'
  }
  const snipName = (v: string) => {
    const first = v.split('\n')[0].slice(0,22).trim()
    return first ? 'snippet · ' + first + (v.length>22 ? '…' : '') : 'snippet.txt'
  }

  const pickFile = (kind: Attachment['kind']) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    files.forEach(f => addAttachment({ kind, name: f.name, meta: humanSize(f.size) }))
    e.target.value = ''
  }

  const commitInline = () => {
    const v = inlineVal.trim()
    if (v) {
      if (inlineMode === 'path') addAttachment({ kind: 'path', name: v, meta: 'path' })
      else addAttachment({ kind: 'snippet', name: snipName(v), meta: v.length + ' chars' })
    }
    setInlineVal(''); setInlineMode(null)
  }

  const send = useCallback(() => {
    const v = chatInput.trim()
    if (!v && attachments.length === 0) return

    // Build the user message text (include attachment names if any)
    const attNote = attachments.length > 0
      ? (v ? ' ' : '') + '[' + attachments.map(a => a.name).join(', ') + ']'
      : ''
    const userText = v + attNote

    const userMsg: ChatMsg = { id: `u-${Date.now()}`, who: 'user', text: userText }
    setMessages(prev => [...prev, userMsg])
    setChatInput('')
    fire()

    // Accumulate context text
    const newText = phase === 'build' ? v : (text ? text + '\n' + v : v)
    setText(newText)

    // Interpret or refine
    setPhase('interpreting')
    const delay = phase === 'understood' ? 700 : 1100

    setTimeout(() => {
      if (phase === 'understood' && u) {
        const { u: nu, reply } = applyFreeRefine(u, v)
        setU(nu)
        const aiMsg: ChatMsg = { id: `a-${Date.now()}`, who: 'ai', text: reply, card: nu }
        setMessages(prev => [...prev, aiMsg])
      } else {
        const nu = interpret(newText, attachments, presetId)
        setU(nu)
        const aiMsg: ChatMsg = { id: `a-${Date.now()}`, who: 'ai', text: "Here's what I'll run:", card: nu }
        setMessages(prev => [...prev, aiMsg])
        if (presetId) setPresetId(null)
      }
      setPhase('understood')
      fire()
    }, delay)
  }, [chatInput, attachments, phase, text, u, presetId])

  const chipRefine = useCallback((r: Refinement) => {
    if (!u) return
    const nu = r.apply(u)
    setU(nu)
    const userMsg: ChatMsg = { id: `u-${Date.now()}`, who: 'user', text: r.label }
    const aiMsg: ChatMsg = { id: `a-${Date.now()}`, who: 'ai', text: r.reply, card: nu }
    setMessages(prev => [...prev, userMsg, aiMsg])
    fire()
  }, [u])

  const handlePreset = (p: Preset) => {
    setPresetId(p.id)
    setChatInput(p.seed)
    inputRef.current?.focus()
  }

  const doLaunch = () => { setShowLaunch(true); fire() }

  const handleConfirmLaunch = async () => {
    setShowLaunch(false)
    setLaunching(true)
    try {
      const res = await apiFetch('/api/v1/sim-sessions', {
        method: 'POST',
        body: JSON.stringify({ brief: u, attachments }),
      })
      const json = await res.json()
      if (json.data?.session_id) {
        const scenarioType: string = json.data.scenario_type ?? 'custom'
        const levelMap: Record<string, string> = {
          pitch: 'entry_junior', behavioral: 'mid_level',
          mr_review: 'senior', system_design: 'senior',
          teaching: 'mid_level', negotiation: 'mid_level',
        }
        const level = levelMap[scenarioType] ?? 'mid_level'
        const character = pickCharacter(json.data.session_id, level)
        setSession(
          json.data.session_id,
          json.data.persona ?? '',
          json.data.time_budget_seconds ?? null,
          scenarioType,
          character.id,
        )
      }
    } catch (e) {
      console.error('[SimulationBuilder] launch failed', e)
    }
    if (onLaunch) onLaunch({ text, attachments, understood: u })
  }

  return (
    <div className="sim-stage">
      {/* top bar */}
      <div className="sim-topbar">
        <div className="brandmark">
          <img src="./icon-mark.svg" width={20} height={20} alt="" style={{ display: "block", flexShrink: 0 }} />
          Simulator
        </div>
        <div className="statusline">
          <span className="status-pill"><span className="live-dot"></span> neural core online</span>
          <span style={{color:'var(--ink-ghost)'}}>v2.4 · context engine</span>
        </div>
      </div>

      <div className="sim-layout">
        {/* ─── chat column ─── */}
        <div className="builder" style={{ overflow: 'hidden' }}>

          {/* messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
            {messages.map(m => <ChatBubble key={m.id} msg={m} onChip={chipRefine} />)}
            {phase === 'interpreting' && <ThinkingBubble />}
            <div ref={chatEndRef} />
          </div>

          {/* quick-start presets — only before first send */}
          {phase === 'build' && messages.length === 1 && (
            <div style={{ padding: '0 28px 12px', display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {PRESETS.filter(p => p.seed).map(p => (
                <button key={p.id} onClick={() => handlePreset(p)} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '5px 12px',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid var(--line-2)',
                  borderRadius: 20,
                  color: 'var(--ink-dim)',
                  fontSize: 11.5,
                  cursor: 'pointer',
                  fontFamily: 'var(--mono)',
                  letterSpacing: '0.03em',
                  transition: 'all 0.14s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--line-hot)'; e.currentTarget.style.color = 'var(--cy)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--line-2)'; e.currentTarget.style.color = 'var(--ink-dim)' }}
                >
                  <Icon name={p.icon} size={12} />
                  {p.title}
                </button>
              ))}
            </div>
          )}

          {/* attachment chips */}
          {attachments.length > 0 && (
            <div className="attach-tray" style={{ padding: '6px 28px', borderTop: '1px solid var(--line)' }}>
              {attachments.map((a, i) => (
                <span className={'chip ' + (a.kind === 'image' ? 'img' : a.kind === 'path' ? 'path' : a.kind === 'file' ? 'file' : '')} key={i}>
                  <span className="chip-ic"><Icon name={a.kind==='image'?'image':a.kind==='path'?'path':a.kind==='snippet'?'snippet':'file'} size={13} /></span>
                  <span className="nm">{a.name}</span>
                  {a.meta && <span className="faint" style={{fontSize:9.5}}>{a.meta}</span>}
                  <span className="x" onClick={() => removeAttachment(i)}>×</span>
                </span>
              ))}
            </div>
          )}

          {/* inline path/snippet input */}
          {inlineMode && (
            <div className="path-input" style={{ margin: '0 28px 8px' }}>
              <Icon name={inlineMode==='path'?'path':'snippet'} size={14} className={inlineMode==='path'?'vi':'cy'} />
              <input
                ref={inlineRef}
                value={inlineVal}
                onChange={e => setInlineVal(e.target.value)}
                onKeyDown={e => { if (e.key==='Enter') commitInline(); if (e.key==='Escape') { setInlineMode(null); setInlineVal('') } }}
                placeholder={inlineMode==='path' ? '/repo/src/file.py  or  github.com/org/repo' : 'paste a snippet, error log, or note…'}
              />
              <button className="tool-btn" onClick={commitInline} style={{padding:'5px 9px'}}>add</button>
            </div>
          )}

          {/* input area */}
          <div style={{ padding: '12px 16px 14px', borderTop: '1px solid var(--line)' }}>
            {/* attachment toolbar */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
              <button className="tool-btn" onClick={() => fileRef.current?.click()}><Icon name="file" size={13} /> File</button>
              <button className="tool-btn" onClick={() => setInlineMode(inlineMode==='path'?null:'path')}><Icon name="path" size={13} /> Path</button>
              <button className="tool-btn" onClick={() => imgRef.current?.click()}><Icon name="image" size={13} /> Image</button>
              <button className="tool-btn" onClick={() => setInlineMode(inlineMode==='snippet'?null:'snippet')}><Icon name="snippet" size={13} /> Snippet</button>
            </div>
            {/* text + send */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <textarea
                ref={inputRef}
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder={phase === 'understood' ? 'Refine the brief…' : 'Describe what you want to rehearse…'}
                rows={2}
                style={{
                  flex: 1, resize: 'none',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--line-2)',
                  borderRadius: 8,
                  padding: '10px 13px',
                  color: 'var(--ink)',
                  fontFamily: 'var(--mono)',
                  fontSize: 13.5,
                  lineHeight: 1.55,
                  outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = 'var(--line-hot)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--line-2)' }}
              />
              <button
                onClick={send}
                disabled={phase === 'interpreting' || (!chatInput.trim() && attachments.length === 0)}
                className="sim-btn btn-primary"
                style={{ padding: '10px 16px', alignSelf: 'stretch' }}
              >
                <Icon name="send" size={14} />
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 7 }}>
              <span style={{ fontSize: 10.5, color: 'var(--ink-ghost)', letterSpacing: '0.05em' }}>
                ↵ send · shift+↵ newline
              </span>
              {phase === 'understood' && (
                <button
                  className="sim-btn btn-launch"
                  onClick={doLaunch}
                  style={{ padding: '6px 16px', fontSize: 12 }}
                >
                  <Icon name="play" size={14} /> Start Session
                </button>
              )}
            </div>
          </div>

          <input ref={fileRef} type="file" multiple hidden onChange={pickFile('file')} />
          <input ref={imgRef} type="file" accept="image/*" multiple hidden onChange={pickFile('image')} />
        </div>

        {/* ─── brain panel (untouched) ─── */}
        <div className="brainwrap">
          <div className="brain-hud">
            <div className="brain-hud-inner">
              <span>core state</span>
              <span className="brain-state-word" style={{color: word==='ready'||word==='synthesizing' ? 'var(--vi)' : 'var(--cy)'}}>{word}</span>
            </div>
          </div>

          <BrainViz level={level} burst={burst} onStats={setStats} />

          <div className="telemetry">
            <div className="gauge">
              <div className="gauge-top">
                <span className="gauge-label">context absorbed</span>
                <span className="gauge-val mono-num">{Math.round(level*100)}%</span>
              </div>
              <div className="gauge-track"><div className="gauge-fill" style={{width:(level*100)+'%'}}></div></div>
            </div>
            <div className="tele-row">
              <div className="stat-cluster">
                <div className="stat"><b className="mono-num">{stats.active}<span style={{color:'var(--ink-ghost)',fontSize:13}}>/{stats.nodes}</span></b><span>neurons live</span></div>
                <div className="stat"><b className="mono-num">{stats.edges}</b><span>synapses</span></div>
                <div className="stat"><b className="mono-num">{stats.pulses}</b><span>signals/frame</span></div>
              </div>
            </div>
            <div style={{display:'flex', flexDirection:'column', gap:8}}>
              <span className="gauge-label">detected signals</span>
              <div className="signals">
                {signals.length===0
                  ? <span className="signal-empty">— waiting for context —</span>
                  : signals.map(s => <span key={s.tag} className={'signal'+(s.vi?' vi':'')}>{s.tag}</span>)}
              </div>
            </div>
            <button
              className="sim-btn btn-launch btn-block"
              style={{marginTop:4}}
              disabled={phase!=='understood'}
              onClick={doLaunch}
            >
              <Icon name="play" size={16} /> {phase==='understood' ? 'Start Session' : 'Describe your scenario first'}
            </button>
          </div>
        </div>
      </div>

      {showLaunch && (
        <LaunchOverlay u={u} onClose={() => setShowLaunch(false)} onConfirm={handleConfirmLaunch} />
      )}

      {launching && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          background: '#05090f',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 24,
          fontFamily: "'DM Mono', monospace",
        }}>
          <div style={{
            width: 52, height: 52, borderRadius: '50%',
            border: '2px solid rgba(34,211,238,0.12)',
            borderTopColor: '#22d3ee',
            animation: 'spin 1s linear infinite',
          }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.82rem', color: '#94a3b8', letterSpacing: '0.06em', marginBottom: 6 }}>
              Setting up your session…
            </div>
            <div style={{ fontSize: '0.62rem', color: '#334155', letterSpacing: '0.04em' }}>
              Briefing the interviewer
            </div>
          </div>
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      )}
    </div>
  )
}
