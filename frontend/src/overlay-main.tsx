import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { OverlayShell } from './components/devcore/OverlayShell'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <OverlayShell />
  </StrictMode>,
)
