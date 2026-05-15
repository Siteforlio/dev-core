import React from 'react'

export interface CharacterDef {
  id: number
  name: string
  title: string
  bg: string
  Face: React.FC
}

// ── Reusable face-part components ────────────────────────────────────────────

const FaceBase: React.FC<{ skin: string }> = ({ skin }) => (
  <>
    <ellipse cx="40" cy="46" rx="23" ry="28" fill={skin} />
    <ellipse cx="17" cy="46" rx="4" ry="5.5" fill={skin} />
    <ellipse cx="63" cy="46" rx="4" ry="5.5" fill={skin} />
  </>
)

const Eyes: React.FC<{ iris: string }> = ({ iris }) => (
  <>
    <ellipse cx="31" cy="40" rx="5" ry="4" fill="white" />
    <ellipse cx="49" cy="40" rx="5" ry="4" fill="white" />
    <circle cx="31" cy="40" r="3" fill={iris} />
    <circle cx="49" cy="40" r="3" fill={iris} />
    <circle cx="31.5" cy="40.5" r="1.5" fill="#0a0a0a" />
    <circle cx="49.5" cy="40.5" r="1.5" fill="#0a0a0a" />
    <circle cx="32.8" cy="39" r="0.8" fill="rgba(255,255,255,0.9)" />
    <circle cx="50.8" cy="39" r="0.8" fill="rgba(255,255,255,0.9)" />
  </>
)

const Brows: React.FC<{ c: string }> = ({ c }) => (
  <>
    <path d="M26 35 Q31 32 36 35" stroke={c} strokeWidth="1.8" fill="none" strokeLinecap="round" />
    <path d="M44 35 Q49 32 54 35" stroke={c} strokeWidth="1.8" fill="none" strokeLinecap="round" />
  </>
)

const Nose: React.FC<{ c: string }> = ({ c }) => (
  <path d="M38.5 47 L37 53 L43 53" stroke={c} strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
)

const SmileMouth: React.FC<{ c: string }> = ({ c }) => (
  <path d="M31 58 Q40 66 49 58" stroke={c} strokeWidth="2.2" fill="none" strokeLinecap="round" />
)

const NeutralMouth: React.FC<{ c: string }> = ({ c }) => (
  <path d="M32 59 Q40 63 48 59" stroke={c} strokeWidth="2" fill="none" strokeLinecap="round" />
)

const FirmMouth: React.FC<{ c: string }> = ({ c }) => (
  <path d="M33 59 Q40 60 47 59" stroke={c} strokeWidth="2" fill="none" strokeLinecap="round" />
)

const Glasses: React.FC = () => (
  <>
    <rect x="24" y="36" width="13" height="9" rx="3" fill="none" stroke="#4a5060" strokeWidth="1.8" />
    <rect x="43" y="36" width="13" height="9" rx="3" fill="none" stroke="#4a5060" strokeWidth="1.8" />
    <line x1="37" y1="40.5" x2="43" y2="40.5" stroke="#4a5060" strokeWidth="1.5" />
    <line x1="10" y1="40.5" x2="24" y2="40.5" stroke="#4a5060" strokeWidth="1.2" />
    <line x1="56" y1="40.5" x2="70" y2="40.5" stroke="#4a5060" strokeWidth="1.2" />
  </>
)

const Beard: React.FC<{ c: string }> = ({ c }) => (
  <path d="M19 58 Q21 73 40 75 Q59 73 61 58 Q54 65 40 66 Q26 65 19 58Z" fill={c} opacity={0.9} />
)

// ── Hair styles ───────────────────────────────────────────────────────────────

const LongHair: React.FC<{ c: string }> = ({ c }) => (
  <path d="M13,66 Q12,14 40,11 Q68,14 67,66 Q64,20 55,13 Q48,8 40,8 Q32,8 25,13 Q16,20 13,66Z" fill={c} />
)

const ShortHair: React.FC<{ c: string }> = ({ c }) => (
  <path d="M16,42 Q15,10 40,9 Q65,10 64,42 Q62,18 54,13 Q48,9 40,9 Q32,9 26,13 Q18,18 16,42Z" fill={c} />
)

const WavyHair: React.FC<{ c: string }> = ({ c }) => (
  <>
    <path d="M13,56 Q12,14 40,11 Q68,14 67,56 Q64,18 55,13 Q48,8 40,8 Q32,8 25,13 Q16,18 13,56Z" fill={c} />
    <path d="M13,56 Q11,48 14,40" stroke={c} strokeWidth="5" fill="none" strokeLinecap="round" />
    <path d="M67,56 Q69,48 66,40" stroke={c} strokeWidth="5" fill="none" strokeLinecap="round" />
  </>
)

const BunHair: React.FC<{ c: string }> = ({ c }) => (
  <>
    <path d="M18,38 Q18,14 40,14 Q62,14 62,38 Q60,20 40,20 Q20,20 18,38Z" fill={c} />
    <circle cx="40" cy="8" r="9" fill={c} />
    <circle cx="40" cy="8" r="5" fill={c} opacity={0.5} />
  </>
)

const FadeHair: React.FC<{ c: string }> = ({ c }) => (
  <path d="M19,44 Q19,16 40,16 Q61,16 61,44 Q59,22 40,22 Q21,22 19,44Z" fill={c} />
)

const SidePartHair: React.FC<{ c: string; skin: string }> = ({ c, skin }) => (
  <>
    <path d="M16,44 Q14,12 40,11 Q66,12 65,44 Q63,18 52,14 Q45,11 38,12 Q26,14 18,24 Q15,32 16,44Z" fill={c} />
    <path d="M38,11 Q39,18 38,28" stroke={skin} strokeWidth="1.5" fill="none" />
  </>
)

const CurlyHair: React.FC<{ c: string }> = ({ c }) => (
  <>
    <path d="M14,42 Q12,16 40,12 Q68,16 66,42 Q62,10 50,7 Q44,4 40,5 Q36,4 30,7 Q18,10 14,42Z" fill={c} />
    <circle cx="21" cy="17" r="8" fill={c} />
    <circle cx="34" cy="10" r="9" fill={c} />
    <circle cx="48" cy="10" r="9" fill={c} />
    <circle cx="60" cy="17" r="8" fill={c} />
  </>
)

const AfroHair: React.FC<{ c: string }> = ({ c }) => (
  <>
    <ellipse cx="40" cy="22" rx="28" ry="21" fill={c} />
    <ellipse cx="16" cy="32" rx="12" ry="10" fill={c} />
    <ellipse cx="64" cy="32" rx="12" ry="10" fill={c} />
  </>
)

const PonytailHair: React.FC<{ c: string }> = ({ c }) => (
  <>
    <path d="M18,38 Q18,12 40,12 Q62,12 62,38 Q60,18 40,18 Q20,18 18,38Z" fill={c} />
    <path d="M40,16 Q46,34 44,52" stroke={c} strokeWidth="7" fill="none" strokeLinecap="round" />
    <ellipse cx="41" cy="16" rx="5" ry="2.5" fill={c} />
  </>
)

const SilverShortHair: React.FC<{ c: string }> = ({ c }) => (
  <>
    <path d="M16,42 Q15,10 40,9 Q65,10 64,42 Q62,18 54,13 Q48,9 40,9 Q32,9 26,13 Q18,18 16,42Z" fill={c} />
    <path d="M26,12 Q27,20 26,30" stroke="rgba(255,255,255,0.22)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
    <path d="M40,10 Q41,18 40,28" stroke="rgba(255,255,255,0.22)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
    <path d="M54,12 Q53,20 54,30" stroke="rgba(255,255,255,0.22)" strokeWidth="2.5" fill="none" strokeLinecap="round" />
  </>
)

// ── 15 Character face components ─────────────────────────────────────────────

// 0 — Maya · HR Recruiter · light warm skin, long dark hair, warm smile
const MayaFace: React.FC = () => {
  const skin = '#f0d0a0', hair = '#1a0800', shadow = '#c8a060', eyes = '#5a3010'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <LongHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <SmileMouth c={shadow} />
    </svg>
  )
}

// 1 — James · Technical Recruiter · medium brown skin, short fade, neutral
const JamesFace: React.FC = () => {
  const skin = '#d49070', hair = '#0d0d0d', shadow = '#a86840', eyes = '#3a1a00'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <FadeHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
    </svg>
  )
}

// 2 — Zoe · Junior Engineer · fair skin, wavy auburn hair, smile
const ZoeFace: React.FC = () => {
  const skin = '#f5e0c0', hair = '#b05828', shadow = '#d4a880', eyes = '#4a3020'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <WavyHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <SmileMouth c={shadow} />
    </svg>
  )
}

// 3 — Priya · Software Engineer · medium brown skin, dark bun, glasses, neutral
const PriyaFace: React.FC = () => {
  const skin = '#c88040', hair = '#0d0d0d', shadow = '#9a6020', eyes = '#2a1000'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <BunHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
      <Glasses />
    </svg>
  )
}

// 4 — Alex · Mid-Level Engineer · medium fair skin, wavy brown hair, neutral
const AlexFace: React.FC = () => {
  const skin = '#f0d8b0', hair = '#7a4828', shadow = '#c8a870', eyes = '#3a2808'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <WavyHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
    </svg>
  )
}

// 5 — Marcus · Engineering Manager · deep brown skin, fade, neutral
const MarcusFace: React.FC = () => {
  const skin = '#7a4030', hair = '#0d0d0d', shadow = '#5a2818', eyes = '#1a0800'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <FadeHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
    </svg>
  )
}

// 6 — Jordan · Staff Engineer · medium tan skin, short hair + full beard, neutral
const JordanFace: React.FC = () => {
  const skin = '#e0a870', hair = '#1a0a00', shadow = '#b87840', eyes = '#3a2010'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <ShortHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
      <Beard c={hair} />
    </svg>
  )
}

// 7 — Chen · Principal Engineer · light skin, neat short dark hair, serious
const ChenFace: React.FC = () => {
  const skin = '#f0e0c8', hair = '#0a0a0a', shadow = '#c8b090', eyes = '#1a1a2a'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <ShortHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <FirmMouth c={shadow} />
    </svg>
  )
}

// 8 — Leila · Senior Engineer · olive skin, dark ponytail, neutral
const LeilaFace: React.FC = () => {
  const skin = '#c8a060', hair = '#1a1010', shadow = '#9a7830', eyes = '#2a1808'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <PonytailHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
    </svg>
  )
}

// 9 — Tom · Director of Engineering · medium skin, salt-pepper short hair, neutral
const TomFace: React.FC = () => {
  const skin = '#d0a070', hair = '#787068', shadow = '#a87840', eyes = '#2a2010'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <SilverShortHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
    </svg>
  )
}

// 10 — Sofia · Director of Engineering · warm olive skin, dark bun, serious
const SofiaFace: React.FC = () => {
  const skin = '#c89858', hair = '#110d0a', shadow = '#9a7030', eyes = '#2a1400'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <BunHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <FirmMouth c={shadow} />
    </svg>
  )
}

// 11 — David · VP of Engineering · medium warm skin, curly hair + beard, startup energy
const DavidFace: React.FC = () => {
  const skin = '#e8c880', hair = '#5c3818', shadow = '#c0a040', eyes = '#3a2808'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <CurlyHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <NeutralMouth c={shadow} />
      <Beard c={hair} />
    </svg>
  )
}

// 12 — Aisha · VP Engineering · deep brown skin, natural afro, firm
const AishaFace: React.FC = () => {
  const skin = '#7a3a20', hair = '#0d0d0d', shadow = '#5a2810', eyes = '#1a0800'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <AfroHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <FirmMouth c={shadow} />
    </svg>
  )
}

// 13 — Raj · Chief Technology Officer · warm brown skin, neat side part, serious
const RajFace: React.FC = () => {
  const skin = '#b87840', hair = '#0d0d0d', shadow = '#8a5820', eyes = '#1a1000'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <SidePartHair c={hair} skin={skin} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <FirmMouth c={shadow} />
    </svg>
  )
}

// 14 — Nina · Chief Executive Officer · light-medium skin, silver short hair, authoritative
const NinaFace: React.FC = () => {
  const skin = '#e0c090', hair = '#b0aea8', shadow = '#b89060', eyes = '#303050'
  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }}>
      <SilverShortHair c={hair} />
      <FaceBase skin={skin} />
      <Brows c={hair} />
      <Eyes iris={eyes} />
      <Nose c={shadow} />
      <FirmMouth c={shadow} />
    </svg>
  )
}

// ── Character definitions ─────────────────────────────────────────────────────

export const CHARACTERS: CharacterDef[] = [
  // Entry / Junior group (0-2)
  { id: 0,  name: 'Maya',   title: 'HR Recruiter',            bg: 'linear-gradient(160deg,#16161e,#1a1520)', Face: MayaFace },
  { id: 1,  name: 'James',  title: 'Technical Recruiter',     bg: 'linear-gradient(160deg,#141820,#101418)', Face: JamesFace },
  { id: 2,  name: 'Zoe',    title: 'Junior Engineer',         bg: 'linear-gradient(160deg,#16181e,#121620)', Face: ZoeFace },
  // Mid-level group (3-5)
  { id: 3,  name: 'Priya',  title: 'Software Engineer',       bg: 'linear-gradient(160deg,#141622,#10141e)', Face: PriyaFace },
  { id: 4,  name: 'Alex',   title: 'Mid-Level Engineer',      bg: 'linear-gradient(160deg,#161820,#121618)', Face: AlexFace },
  { id: 5,  name: 'Marcus', title: 'Engineering Manager',     bg: 'linear-gradient(160deg,#141618,#101214)', Face: MarcusFace },
  // Senior group (6-8)
  { id: 6,  name: 'Jordan', title: 'Staff Engineer',          bg: 'linear-gradient(160deg,#161820,#12161e)', Face: JordanFace },
  { id: 7,  name: 'Chen',   title: 'Principal Engineer',      bg: 'linear-gradient(160deg,#141618,#101316)', Face: ChenFace },
  { id: 8,  name: 'Leila',  title: 'Senior Engineer',         bg: 'linear-gradient(160deg,#161a22,#12161e)', Face: LeilaFace },
  // Lead / Manager group (9-11)
  { id: 9,  name: 'Tom',    title: 'Director of Engineering', bg: 'linear-gradient(160deg,#161820,#12161a)', Face: TomFace },
  { id: 10, name: 'Sofia',  title: 'Director of Engineering', bg: 'linear-gradient(160deg,#141618,#101214)', Face: SofiaFace },
  { id: 11, name: 'David',  title: 'VP of Engineering',       bg: 'linear-gradient(160deg,#16181e,#121618)', Face: DavidFace },
  // Director / VP / C-Suite group (12-14)
  { id: 12, name: 'Aisha',  title: 'VP Engineering',          bg: 'linear-gradient(160deg,#141618,#101214)', Face: AishaFace },
  { id: 13, name: 'Raj',    title: 'Chief Technology Officer',bg: 'linear-gradient(160deg,#161820,#12161a)', Face: RajFace },
  { id: 14, name: 'Nina',   title: 'Chief Executive Officer', bg: 'linear-gradient(160deg,#141618,#101214)', Face: NinaFace },
]

// ── Character selection ───────────────────────────────────────────────────────

const LEVEL_BASE: Record<string, number> = {
  entry_junior:        0,
  mid_level:           3,
  senior:              6,
  lead_manager:        9,
  director_vp_csuite: 12,
}

/** Deterministically picks one of the 3 characters in the level group, seeded by sessionId. */
export function pickCharacter(sessionId: string, level: string): CharacterDef {
  const base = LEVEL_BASE[level] ?? 0
  let hash = 0
  for (let i = 0; i < sessionId.length; i++) {
    hash = (hash * 31 + sessionId.charCodeAt(i)) >>> 0
  }
  return CHARACTERS[base + (hash % 3)]
}
