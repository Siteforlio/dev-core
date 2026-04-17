import { useState, useRef } from 'react'
import { useJobHunter } from '../../hooks/useJobHunter'

interface Props {
  onComplete: () => void
}

export default function ProfileOnboarding({ onComplete }: Props) {
  const { upsertProfile, parseResume, parseResumeFile } = useJobHunter()
  const [resumeText, setResumeText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [fields, setFields] = useState<Record<string, unknown>>({})
  const [missingFields, setMissingFields] = useState<string[]>([])
  const [completionScore, setCompletionScore] = useState(0)
  const [parseError, setParseError] = useState('')
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleParse = async () => {
    if (!resumeText.trim()) return
    setParsing(true)
    setParseError('')
    try {
      const extracted = await parseResume(resumeText)
      setFields((prev) => ({ ...prev, ...extracted }))
    } catch {
      setParseError('Failed to parse resume. Please check the backend is running.')
    } finally {
      setParsing(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setParsing(true)
    setParseError('')
    setUploadedFileName(file.name)
    try {
      const extracted = await parseResumeFile(file)
      setFields((prev) => ({ ...prev, ...extracted }))
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Failed to parse file.')
      setUploadedFileName(null)
    } finally {
      setParsing(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setParseError('')
    try {
      const result = await upsertProfile(fields)
      setCompletionScore(result.completionScore)
      setMissingFields(result.missingFields)
      if (result.isComplete) {
        onComplete()
      }
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Failed to save profile. Is the backend running?')
    } finally {
      setSaving(false)
    }
  }

  const setField = (key: string, value: unknown) => {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="max-w-2xl mx-auto w-full px-4 py-8 flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Let's set up your profile</h2>
        <p className="text-gray-400 text-sm mt-1">
          Complete your profile once and the Job Hunter applies to hundreds of roles automatically.
        </p>
      </div>

      {completionScore > 0 && (
        <div className="flex items-center gap-3">
          <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all"
              style={{ width: `${completionScore}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 flex-shrink-0">{completionScore}% complete</span>
        </div>
      )}

      {missingFields.length > 0 && (
        <div className="bg-yellow-900/30 border border-yellow-800 rounded-lg px-4 py-3">
          <p className="text-xs text-yellow-300 font-medium mb-1">Still needed:</p>
          <p className="text-xs text-yellow-400">{missingFields.join(', ')}</p>
        </div>
      )}

      {/* Resume input — file upload or paste */}
      <div className="flex flex-col gap-3">
        <span className="text-xs text-gray-400 uppercase tracking-wide">Import Resume</span>

        {/* File upload */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-3 border border-dashed border-gray-700 hover:border-blue-600 rounded-lg px-4 py-4 cursor-pointer transition-colors group"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-500 group-hover:text-blue-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <div className="min-w-0">
            {uploadedFileName ? (
              <p className="text-sm text-blue-400 truncate">{uploadedFileName}</p>
            ) : (
              <>
                <p className="text-sm text-gray-300">Upload resume file</p>
                <p className="text-xs text-gray-600">PDF, DOCX, or TXT — max 5 MB</p>
              </>
            )}
          </div>
          {parsing && (
            <div className="ml-auto w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Divider */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-px bg-gray-800" />
          <span className="text-xs text-gray-600">or paste text</span>
          <div className="flex-1 h-px bg-gray-800" />
        </div>

        {/* Text paste */}
        <textarea
          className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded-lg p-3 h-36 resize-none focus:outline-none focus:border-blue-600 placeholder-gray-600"
          placeholder="Paste your resume text here…"
          value={resumeText}
          onChange={(e) => setResumeText(e.target.value)}
        />
        {parseError && <p className="text-xs text-red-400">{parseError}</p>}
        <button
          onClick={handleParse}
          disabled={!resumeText.trim() || parsing}
          className="self-start text-sm bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          {parsing ? 'Parsing…' : 'Parse Text'}
        </button>
      </div>

      {/* Contact fields */}
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-gray-300">Contact Info</h3>
        <div className="grid grid-cols-2 gap-3">
          {['full_name', 'email', 'phone', 'city', 'country', 'linkedin_url', 'github_url'].map((key) => (
            <div key={key} className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 capitalize">{key.replace(/_/g, ' ')}</label>
              <input
                type="text"
                value={(fields[key] as string) ?? ''}
                onChange={(e) => setField(key, e.target.value)}
                className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-600"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Skills */}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-gray-300">Skills</h3>
        <p className="text-xs text-gray-500">Comma-separated — languages, frameworks, tools</p>
        <input
          type="text"
          value={
            Array.isArray(fields.skills)
              ? (fields.skills as string[]).join(', ')
              : ((fields.skills as string) ?? '')
          }
          onChange={(e) =>
            setField(
              'skills',
              e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
            )
          }
          placeholder="React, TypeScript, Python, FastAPI, PostgreSQL…"
          className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-600"
        />
      </div>

      {/* Languages spoken */}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-gray-300">Languages Spoken</h3>
        <p className="text-xs text-gray-500">Comma-separated (min 1)</p>
        <input
          type="text"
          value={
            Array.isArray(fields.languages_spoken)
              ? (fields.languages_spoken as { language: string }[])
                  .map((l) => (typeof l === 'string' ? l : l.language))
                  .join(', ')
              : ''
          }
          onChange={(e) =>
            setField(
              'languages_spoken',
              e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean)
                .map((lang) => ({ language: lang, proficiency: 'conversational' }))
            )
          }
          placeholder="English, Spanish, French…"
          className="bg-gray-900 border border-gray-800 text-gray-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-600"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="self-start bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors"
      >
        {saving ? 'Saving…' : 'Save Profile'}
      </button>
    </div>
  )
}
