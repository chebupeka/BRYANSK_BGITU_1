import { useEffect, useRef } from 'react';
import { useMediaQuery, useReducedMotion } from '../lib/hooks';

/**
 * A small, soft halo follows the system pointer without covering nearby content.
 */
export default function CursorBeam() {
  const ref = useRef<HTMLDivElement>(null);
  const fine = useMediaQuery('(hover: hover) and (pointer: fine)');
  const reduced = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node || !fine) return;

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let targetX = x;
    let targetY = y;
    let placed = false;
    let frame = 0;

    function move(event: PointerEvent) {
      targetX = event.clientX;
      targetY = event.clientY;
      if (!placed) {
        x = targetX;
        y = targetY;
        placed = true;
        node!.style.opacity = '1';
      }
    }
    function leave() { node!.style.opacity = '0'; placed = false; }

    function loop() {
      frame = requestAnimationFrame(loop);
      const ease = reduced ? 1 : 0.2;
      x += (targetX - x) * ease;
      y += (targetY - y) * ease;
      node!.style.setProperty('--beam-x', `${x.toFixed(1)}px`);
      node!.style.setProperty('--beam-y', `${y.toFixed(1)}px`);
    }

    window.addEventListener('pointermove', move, { passive: true });
    document.addEventListener('pointerleave', leave);
    frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', move);
      document.removeEventListener('pointerleave', leave);
    };
  }, [fine, reduced]);

  if (!fine) return null;
  return <div className="cursor-beam" ref={ref} aria-hidden="true" />;
}
