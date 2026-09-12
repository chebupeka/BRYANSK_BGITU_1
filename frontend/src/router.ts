import { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

/** Pages in the order a person walks through them; the order also sets the animation. */
export const ROUTES = ['/', '/catalog', '/draft', '/options', '/result'] as const;
export type Route = (typeof ROUTES)[number];

export const TITLES: Record<Route, string> = {
  '/': 'Документ за 3 шага',
  '/catalog': 'Каталог документов — Документ за 3 шага',
  '/draft': 'Черновик — Документ за 3 шага',
  '/options': 'Тип и реквизиты — Документ за 3 шага',
  '/result': 'Готовый файл — Документ за 3 шага',
};

export function toRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, '') || '/';
  return (ROUTES as readonly string[]).includes(path) ? (path as Route) : '/';
}

type ViewTransitionDocument = Document & {
  startViewTransition?: (callback: () => void) => { finished: Promise<void> };
};

/**
 * Swaps the page inside a view transition, so the browser cross-fades the old frame into the
 * new one and the CSS in shell.css can turn that into a move through depth. Without support
 * for view transitions — or with reduced motion — the page simply changes.
 */
function animate(direction: 'forward' | 'back', update: () => void): void {
  const root = document.documentElement;
  root.dataset.nav = direction;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const start = (document as ViewTransitionDocument).startViewTransition;
  if (reduced || typeof start !== 'function') {
    update();
    return;
  }
  start.call(document, () => flushSync(update));
}

export interface Router {
  path: Route;
  /** `replace` is for redirects: they must not add a step to go back to. */
  navigate: (to: Route, replace?: boolean) => void;
  back: () => void;
  /** True once this session has a page to go back to. */
  canGoBack: boolean;
}

export function useRouter(): Router {
  const [path, setPath] = useState<Route>(() => toRoute(window.location.pathname));
  const [depth, setDepth] = useState(0);
  const current = useRef(path);
  current.current = path;

  useEffect(() => {
    function onPopState() {
      const next = toRoute(window.location.pathname);
      const back = ROUTES.indexOf(next) < ROUTES.indexOf(current.current);
      animate(back ? 'back' : 'forward', () => setPath(next));
      setDepth(value => Math.max(0, value - 1));
    }
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => { document.title = TITLES[path]; }, [path]);

  const navigate = useCallback((to: Route, replace = false) => {
    if (to === current.current) return;
    const back = ROUTES.indexOf(to) < ROUTES.indexOf(current.current);
    if (replace) {
      window.history.replaceState({}, '', to);
    } else {
      window.history.pushState({}, '', to);
      setDepth(value => value + 1);
    }
    animate(back ? 'back' : 'forward', () => setPath(to));
  }, []);

  const back = useCallback(() => {
    window.history.back();
  }, []);

  return { path, navigate, back, canGoBack: depth > 0 };
}
