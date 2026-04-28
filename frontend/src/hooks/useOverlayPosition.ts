import { useOverlayStore } from '../store/overlayStore'
import type { OverlayPosition } from '../types/devcore'

const ORDER: OverlayPosition[] = ['top-center', 'top-left', 'top-right', 'bottom-center', 'bottom-right']

export function useOverlayPosition() {
  const { position, setPosition } = useOverlayStore()
  const cycleNext = () => {
    const idx = ORDER.indexOf(position)
    setPosition(ORDER[(idx + 1) % ORDER.length])
  }
  return { position, cycleNext }
}
