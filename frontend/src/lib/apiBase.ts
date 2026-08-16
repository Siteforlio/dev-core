/**
 * Central API base URLs — all frontend code should import from here.
 * In Electron, the main process passes the backend port via electronAPI.
 * In plain browser dev mode, defaults to localhost:8000.
 */

function getPort(): number {
  return (window as any).electronAPI?.backendPort ?? 8000
}

export function API_BASE(): string {
  return `http://localhost:${getPort()}/api/v1`
}

export function API_ROOT(): string {
  return `http://localhost:${getPort()}`
}

export function WS_BASE(): string {
  return `ws://localhost:${getPort()}/api/v1`
}
