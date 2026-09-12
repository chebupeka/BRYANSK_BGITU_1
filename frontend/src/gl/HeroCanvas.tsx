import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { startScene, type SceneHandle } from './scene';
import { useReducedMotion } from '../lib/hooks';
import type { ThemeName } from '../types';

interface Props {
  theme: ThemeName;
  muted: boolean;
}

/** One persistent scene across routes; workspace pages soften the composited backdrop. */
export default function HeroCanvas({ theme, muted }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<SceneHandle | null>(null);
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const [supported, setSupported] = useState(true);
  const reduced = useReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let visible = true;

    function syncRunning() {
      sceneRef.current?.setRunning(visible && !document.hidden && !reduced);
    }
    function initialize() {
      sceneRef.current?.destroy();
      sceneRef.current = startScene(canvas!, {
        light: themeRef.current === 'light', reducedMotion: reduced,
      });
      setSupported(Boolean(sceneRef.current));
      syncRunning();
    }
    function onContextLost(event: Event) {
      event.preventDefault();
      sceneRef.current?.destroy();
      sceneRef.current = null;
      setSupported(false);
    }

    initialize();
    const observer = new IntersectionObserver(entries => {
      visible = entries[0]?.isIntersecting ?? true;
      syncRunning();
    });
    observer.observe(canvas);
    document.addEventListener('visibilitychange', syncRunning);
    canvas.addEventListener('webglcontextlost', onContextLost);
    canvas.addEventListener('webglcontextrestored', initialize);

    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', syncRunning);
      canvas.removeEventListener('webglcontextlost', onContextLost);
      canvas.removeEventListener('webglcontextrestored', initialize);
      sceneRef.current?.destroy();
      sceneRef.current = null;
    };
  }, [reduced]);

  useEffect(() => {
    sceneRef.current?.setLight(theme === 'light' ? 1 : 0);
  }, [theme, reduced]);

  return <div className="home-documents" aria-hidden="true" data-muted={muted}>
    <canvas ref={canvasRef} className="home-documents-canvas"
      data-fallback={supported ? undefined : 'css'} />
    {!supported && <div className="home-documents-fallback">
      {Array.from({ length: 12 }, (_, index) => <span key={index} style={{
        left: `${(index * 37 + 7) % 96}%`,
        top: `${(index * 23 + 5) % 100}%`,
        '--paper-angle': `${index * 47 - 60}deg`,
        '--paper-tilt': `${20 + index % 4 * 13}deg`,
      } as CSSProperties} />)}
    </div>}
    <div className="home-documents-veil" />
  </div>;
}
