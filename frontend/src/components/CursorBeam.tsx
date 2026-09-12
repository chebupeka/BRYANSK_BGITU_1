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

    let lastX = 0;
    let lastY = 0;
    let visible = false;
    let frame = 0;
    // `scrollbar-gutter: stable both-edges` on the root insets the box a fixed element is
    // laid out in, so `left: 0` does not sit at `clientX: 0`. Measure where the halo lands
    // with no translate rather than assume the inset, and carry the difference below.
    let originX = 0;
    let originY = 0;

    function measure() {
      node!.style.setProperty('--beam-x', '0px');
      node!.style.setProperty('--beam-y', '0px');
      const box = node!.getBoundingClientRect();
      originX = box.left + box.width / 2;
      originY = box.top + box.height / 2;
    }

    function write() {
      node!.style.setProperty('--beam-x', `${lastX - originX}px`);
      node!.style.setProperty('--beam-y', `${lastY - originY}px`);
    }

    // The halo sits exactly under the pointer: the position is taken from the event itself,
    // written once per frame so a burst of pointer events cannot outrun the paint.
    function place() {
      frame = 0;
      write();
      if (!visible) {
        visible = true;
        node!.style.opacity = '1';
      }
    }

    function move(event: PointerEvent) {
      lastX = event.clientX;
      lastY = event.clientY;
      if (!frame) frame = requestAnimationFrame(place);
    }
    function leave() {
      visible = false;
      node!.style.opacity = '0';
    }
    // A new viewport width can change the gutter. Re-measuring and re-placing within one
    // frame keeps the zeroed translate off the screen.
    function relayout() {
      measure();
      if (visible) write();
    }

    measure();
    window.addEventListener('pointermove', move, { passive: true });
    document.addEventListener('pointerleave', leave);
    window.addEventListener('resize', relayout);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', move);
      document.removeEventListener('pointerleave', leave);
      window.removeEventListener('resize', relayout);
    };
  }, [fine, reduced]);

  if (!fine) return null;
  return <div className="cursor-beam" ref={ref} aria-hidden="true" />;
}
