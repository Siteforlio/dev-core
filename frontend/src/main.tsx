import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// One-time cleanup: remove auth tokens previously persisted to localStorage
// (security hardening 2026-09-03 — tokens now kept in memory only)
if (typeof localStorage !== 'undefined' && localStorage.getItem('auth')) {
  localStorage.removeItem('auth')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
