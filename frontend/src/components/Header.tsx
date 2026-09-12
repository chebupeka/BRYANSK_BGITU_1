import { useEffect, useState } from 'react';
import { Badge } from './ui';
import { ArrowLeft, Moon, Sun } from './icons';
import type { Route } from '../router';
import type { ThemeName } from '../types';

const STEPS: { route: Route; name: string }[] = [
  { route: '/draft', name: 'Черновик' },
  { route: '/options', name: 'Тип и реквизиты' },
  { route: '/result', name: 'Готовый файл' },
];

const PAGES: { route: Route; name: string }[] = [
  { route: '/', name: 'Главная' },
  { route: '/catalog', name: 'Каталог' },
  { route: '/draft', name: 'Студия' },
];

interface Props {
  path: Route;
  /** How far into the three steps the person may jump right now. */
  reachable: number;
  canGoBack: boolean;
  /** The catalog request failed: the backend is not answering at all. */
  offline: boolean;
  processorMode: string;
  theme: ThemeName;
  onNavigate: (route: Route) => void;
  onBack: () => void;
  onTheme: (theme: ThemeName) => void;
}

/** What the processor does to the text right now — the one thing worth stating up front. */
export function processorLabel(mode: string): {
  text: string; tone: 'accent' | 'warn' | 'neutral'; title: string;
} {
  if (mode === 'stub') {
    return {
      text: 'Демо-режим',
      tone: 'neutral',
      title: 'Текст переносится без исправлений: орфография и деловой стиль пока не подключены.',
    };
  }
  if (mode === 'unavailable') {
    return {
      text: 'Обработчик выключен',
      tone: 'warn',
      title: 'Подготовка вернёт ошибку: режим предназначен для проверки обработки отказов.',
    };
  }
  return {
    text: 'Модель включена',
    tone: 'accent',
    title: `Черновик обрабатывает модель (${mode}). Факты берутся только из текста черновика.`,
  };
}

export default function Header(props: Props) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const mode = processorLabel(props.processorMode);
  const inStudio = STEPS.some(step => step.route === props.path);

  return <header className={`app-header ${scrolled ? 'is-scrolled' : ''}`}>
    <div className="header-inner">
      <div className="header-lead">
        {props.canGoBack && <button type="button" className="back-button" onClick={props.onBack}>
          <ArrowLeft size={16} /><span>Назад</span>
        </button>}
        <button type="button" className="brand" onClick={() => props.onNavigate('/')}
          aria-label="Документ за 3 шага — на главную" title="На главную">
          <img src="/favicon.svg" alt="" width="32" height="32" />
          <span className="brand-text">Документ <strong>за 3 шага</strong></span>
        </button>
      </div>

      <nav className="header-nav" aria-label={inStudio ? 'Этапы работы' : 'Разделы'}>
        {inStudio
          ? STEPS.map((step, index) => <button key={step.route} type="button"
            className={`header-step ${step.route === props.path ? 'is-active' : ''}`}
            aria-current={step.route === props.path ? 'step' : undefined}
            disabled={index > props.reachable}
            onClick={() => props.onNavigate(step.route)}>
            <span className="header-step-number">{index + 1}</span>
            <span className="header-step-name">{step.name}</span>
          </button>)
          : PAGES.map(page => <button key={page.name} type="button"
            className={`header-step ${page.route === props.path ? 'is-active' : ''}`}
            aria-current={page.route === props.path ? 'page' : undefined}
            onClick={() => props.onNavigate(page.route)}>
            <span className="header-step-name">{page.name}</span>
          </button>)}
      </nav>

      <div className="header-side">
        <Badge tone={props.offline ? 'warn' : mode.tone}
          title={props.offline ? 'Backend не отвечает. Проверьте, что сервер запущен.' : mode.title}>
          <span className={`status-dot ${props.offline ? 'is-off' : ''}`} aria-hidden="true" />
          {props.offline ? 'Нет связи' : mode.text}
        </Badge>
        <button type="button" className="icon-button"
          onClick={() => props.onTheme(props.theme === 'dark' ? 'light' : 'dark')}
          aria-label={props.theme === 'dark' ? 'Светлое оформление' : 'Тёмное оформление'}
          title={props.theme === 'dark' ? 'Светлое оформление' : 'Тёмное оформление'}>
          {props.theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </div>
  </header>;
}
