import { useCallback, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import type { OnMount } from '@monaco-editor/react'
import type { SkillsTask } from '../../store/interviewStore'
import { useAntiCheat } from '../../hooks/useAntiCheat'

interface Props {
  task: SkillsTask
  sessionId: string
  roundId: string
  cameraOn: boolean
  onSubmit: (submission: string) => void
  disabled?: boolean
}

export default function SkillsTaskEditor({ task, sessionId, roundId, cameraOn, onSubmit, disabled }: Props) {
  const [value, setValue] = useState(task.starter_code ?? '')
  const [submitting, setSubmitting] = useState(false)
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)

  const { onMonacoPaste, onKeyDown } = useAntiCheat({
    sessionId,
    roundId,
    listenDocumentPaste: task.input_type !== 'code', // Monaco handles its own paste
  })

  // Monaco setup
  const handleEditorDidMount: OnMount = useCallback(
    (editor) => {
      editorRef.current = editor

      // Paste detection via Monaco content change diff
      let prevLength = (task.starter_code ?? '').length
      editor.onDidChangeModelContent(() => {
        const newVal = editor.getValue()
        const delta = newVal.length - prevLength
        prevLength = newVal.length
        setValue(newVal)
        // Large positive delta not from typing = paste
        if (delta > 40) {
          onMonacoPaste(newVal.slice(-delta))
        }
      })

      // Key velocity
      editor.onKeyDown(() => onKeyDown())
    },
    [task.starter_code, onMonacoPaste, onKeyDown],
  )

  const handleSubmit = async () => {
    if (disabled || submitting) return
    const submission = task.input_type === 'code'
      ? (editorRef.current?.getValue() ?? value)
      : value
    if (!submission.trim()) return
    setSubmitting(true)
    try {
      await onSubmit(submission)
    } finally {
      setSubmitting(false)
    }
  }

  const cameraWarning = !cameraOn

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: '#0f1117',
      color: '#e2e8f0',
      fontFamily: 'system-ui, sans-serif',
    }}>
      {/* Task brief header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(255,255,255,0.03)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#7c85f0', textTransform: 'uppercase' }}>
            Skills Assessment
          </span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>{task.time_hint}</span>
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#f0f4ff', marginBottom: 8 }}>{task.title}</div>
        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.65)', lineHeight: 1.55 }}>{task.brief}</div>

        {/* Evaluation criteria */}
        {task.evaluation_criteria.length > 0 && (
          <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {task.evaluation_criteria.map((c, i) => (
              <span key={i} style={{
                fontSize: 10,
                padding: '2px 8px',
                borderRadius: 99,
                background: 'rgba(124,133,240,0.15)',
                color: '#9ba3f5',
                border: '1px solid rgba(124,133,240,0.25)',
              }}>
                {c}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Camera warning banner */}
      {cameraWarning && (
        <div style={{
          padding: '8px 20px',
          background: 'rgba(239,68,68,0.12)',
          borderBottom: '1px solid rgba(239,68,68,0.25)',
          fontSize: 12,
          color: '#f87171',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexShrink: 0,
        }}>
          <span>⚠️</span>
          Camera must be on during the skills assessment. Please enable your camera to continue.
        </div>
      )}

      {/* Editor area */}
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        {task.input_type === 'code' ? (
          <Editor
            height="100%"
            language={task.language ?? 'javascript'}
            value={value}
            theme="vs-dark"
            onMount={handleEditorDidMount}
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              lineNumbers: 'on',
              renderLineHighlight: 'line',
              padding: { top: 12, bottom: 12 },
              readOnly: disabled || submitting,
            }}
          />
        ) : (
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={disabled || submitting}
            placeholder="Type your response here..."
            style={{
              width: '100%',
              height: '100%',
              padding: '16px 20px',
              background: '#1a1d27',
              color: '#e2e8f0',
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontSize: 14,
              lineHeight: 1.6,
              fontFamily: 'system-ui, sans-serif',
              boxSizing: 'border-box',
            }}
          />
        )}
      </div>

      {/* Submit bar */}
      <div style={{
        padding: '12px 20px',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        background: '#0f1117',
      }}>
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
          {task.input_type === 'code'
            ? `Language: ${task.language ?? 'any'}`
            : `${value.length} characters`}
        </div>
        <button
          onClick={handleSubmit}
          disabled={disabled || submitting || !value.trim() || cameraWarning}
          style={{
            padding: '8px 24px',
            borderRadius: 8,
            border: 'none',
            background: (disabled || submitting || !value.trim() || cameraWarning)
              ? 'rgba(255,255,255,0.1)'
              : '#7c85f0',
            color: (disabled || submitting || !value.trim() || cameraWarning)
              ? 'rgba(255,255,255,0.3)'
              : '#fff',
            fontWeight: 600,
            fontSize: 13,
            cursor: (disabled || submitting || !value.trim() || cameraWarning) ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {submitting ? 'Submitting…' : 'Submit Solution →'}
        </button>
      </div>
    </div>
  )
}
