import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

/** Every animation in the interface asks this first. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  );
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const listen = () => setReduced(query.matches);
    query.addEventListener('change', listen);
    return () => query.removeEventListener('change', listen);
  }, []);
  return reduced;
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia?.(query).matches ?? false);
  useEffect(() => {
    const media = window.matchMedia(query);
    const listen = () => setMatches(media.matches);
    listen();
    media.addEventListener('change', listen);
    return () => media.removeEventListener('change', listen);
  }, [query]);
  return matches;
}

/** Reveals a section once it scrolls into view, the way the product pages do it. */
export function useReveal<T extends HTMLElement>(): (node: T | null) => void {
  const observer = useRef<IntersectionObserver | null>(null);
  useEffect(() => () => observer.current?.disconnect(), []);
  return useCallback((node: T | null) => {
    if (!node) return;
    if (!observer.current) {
      observer.current = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add('is-revealed');
          observer.current?.unobserve(entry.target);
        }
      }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
    }
    observer.current.observe(node);
  }, []);
}

/** Pointer parallax for a card: writes --tilt-x / --tilt-y, the CSS does the rest. */
export function usePointerTilt<T extends HTMLElement>(strength = 6): {
  ref: React.RefObject<T | null>;
  handlers: { onPointerMove: (event: React.PointerEvent) => void; onPointerLeave: () => void };
} {
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();
  const fine = useMediaQuery('(hover: hover) and (pointer: fine)');
  const onPointerMove = useCallback((event: React.PointerEvent) => {
    const node = ref.current;
    if (!node || reduced || !fine) return;
    const box = node.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    node.style.setProperty('--tilt-x', `${(-y * strength).toFixed(2)}deg`);
    node.style.setProperty('--tilt-y', `${(x * strength).toFixed(2)}deg`);
    node.style.setProperty('--glare-x', `${((x + 0.5) * 100).toFixed(1)}%`);
    node.style.setProperty('--glare-y', `${((y + 0.5) * 100).toFixed(1)}%`);
  }, [reduced, fine, strength]);
  const onPointerLeave = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    node.style.setProperty('--tilt-x', '0deg');
    node.style.setProperty('--tilt-y', '0deg');
  }, []);
  return { ref, handlers: { onPointerMove, onPointerLeave } };
}

/** Width of a box, for scaling the A4 page to whatever room it has. */
export function useElementWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    setWidth(node.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/** Natural height of a box, used to reserve room for a sheet that is scaled by transform. */
export function useElementHeight<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [height, setHeight] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) setHeight(entry.contentRect.height);
    });
    observer.observe(node);
    setHeight(node.getBoundingClientRect().height);
    return () => observer.disconnect();
  }, []);
  return [ref, height];
}

export interface Hotkey {
  /** Lower-case key, e.g. 'enter' or 's'. */
  key: string;
  ctrl?: boolean;
  run: () => void;
}

/** Ctrl+Enter to move on, Ctrl+S to save the file: the keyboard path through the flow. */
export function useHotkeys(hotkeys: Hotkey[]): void {
  const latest = useRef(hotkeys);
  latest.current = hotkeys;
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      for (const hotkey of latest.current) {
        const wantsModifier = hotkey.ctrl ?? false;
        const hasModifier = event.ctrlKey || event.metaKey;
        if (hotkey.key !== key || wantsModifier !== hasModifier) continue;
        event.preventDefault();
        hotkey.run();
        return;
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}

/** Seconds spent waiting, so a long model request does not look frozen. */
export function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      setSeconds(Math.round((Date.now() - started) / 1000));
    }, 250);
    return () => window.clearInterval(timer);
  }, [active]);
  return seconds;
}
