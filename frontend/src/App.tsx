import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  asFailure, downloadDocument, getCatalog, getStatus, processDocument, suggestRequisites,
} from './api';
import Header, { processorLabel } from './components/Header';
import DraftStep from './components/DraftStep';
import OptionsStep from './components/OptionsStep';
import ReviewStep from './components/ReviewStep';
import PreviewPane from './components/PreviewPane';
import CursorBeam from './components/CursorBeam';
import HeroCanvas from './gl/HeroCanvas';
import { Button, Callout, Spinner, Toast } from './components/ui';
import { Refresh } from './components/icons';
import HomePage from './pages/HomePage';
import CatalogPage from './pages/CatalogPage';
import { useElapsedSeconds, useHotkeys } from './lib/hooks';
import { arrangeBlocks, splitParagraphs } from './lib/layout';
import { DEMO_REQUISITES, SAMPLES, sampleFor } from './lib/samples';
import { useRouter, type Route } from './router';
import { loadDraft, loadTheme, saveDraft, saveTheme } from './storage';
import type {
  ApiFailure, Catalog, DocumentContent, ProcessResult, ServiceStatus, ThemeName,
} from './types';

const EMPTY_PAGE = ['Черновик пока пуст. Начните печатать — страница соберётся здесь.'];
const STEP_ROUTES: Route[] = ['/draft', '/options', '/result'];

export default function App() {
  const [state, setState] = useState(loadDraft);
  const [theme, setTheme] = useState<ThemeName>(loadTheme);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogFailure, setCatalogFailure] = useState<ApiFailure | null>(null);
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [outcome, setOutcome] = useState({ cache: '', elapsedMs: 0 });
  const [busy, setBusy] = useState<'process' | 'download' | null>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);
  const [downloadedName, setDownloadedName] = useState('');
  const [saved, setSaved] = useState(true);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [suggestSupported, setSuggestSupported] = useState(true);
  const [suggestBusy, setSuggestBusy] = useState(false);
  const [focusId, setFocusId] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{ message: string; tone: 'info' | 'success' | 'warn' } | null>(null);

  const { path, navigate, back, canGoBack } = useRouter();

  // Which requisites came out of the draft rather than from the keyboard: only these are
  // dropped when the draft changes, so typed values survive an edit of the text.
  const autofilled = useRef<Record<string, string[]>>({});
  const waiting = useElapsedSeconds(busy === 'process');

  const docType = catalog?.doc_types.find(type => type.id === state.docType);
  const template = catalog?.templates.find(item => item.id === state.templateId);
  const requisites = useMemo(
    () => state.requisitesByType[state.docType] ?? {},
    [state.requisitesByType, state.docType],
  );

  const previewContent: DocumentContent = useMemo(() => {
    if (result) return result.document;
    const body = splitParagraphs(state.draft);
    return { doc_type: state.docType, requisites, body: body.length ? body : EMPTY_PAGE };
  }, [result, state.draft, state.docType, requisites]);

  const reachable = result ? 2 : state.draft.trim() ? 1 : 0;

  const reloadCatalog = useCallback(async () => {
    setCatalogFailure(null);
    try {
      const next = await getCatalog();
      if (!next.doc_types.length || !next.templates.length) {
        throw new Error('Каталог документов пока пуст. Проверьте конфигурации backend.');
      }
      setCatalog(next);
      void getStatus().then(setStatus);
      setState(previous => ({
        ...previous,
        docType: next.doc_types.some(type => type.id === previous.docType)
          ? previous.docType : next.doc_types[0].id,
        templateId: next.templates.some(item => item.id === previous.templateId)
          ? previous.templateId : next.templates[0].id,
      }));
    } catch (error) {
      setCatalogFailure(asFailure(error));
    }
  }, []);

  useEffect(() => { void reloadCatalog(); }, [reloadCatalog]);
  useEffect(() => { setSaved(saveDraft(state)); }, [state]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  // A page opened directly still has to be reachable: without a draft there is nothing to
  // set up, without a prepared result there is nothing to download.
  useEffect(() => {
    if (path === '/result' && !result) navigate(state.draft.trim() ? '/options' : '/draft', true);
    else if (path === '/options' && !state.draft.trim()) navigate('/draft', true);
  }, [path, result, state.draft, navigate]);

  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [path]);

  function changeDraft(draft: string) {
    setState(previous => {
      if (draft === previous.draft) return previous;
      const requisitesByType = { ...previous.requisitesByType };
      for (const [type, ids] of Object.entries(autofilled.current)) {
        const fields = { ...(requisitesByType[type] ?? {}) };
        for (const id of ids) delete fields[id];
        requisitesByType[type] = fields;
      }
      return { ...previous, draft, requisitesByType };
    });
    autofilled.current = {};
    setSuggested([]);
    setResult(null);
    setFailure(null);
    setDownloadedName('');
  }

  function changeRequisite(id: string, value: string) {
    autofilled.current[state.docType] = (autofilled.current[state.docType] ?? [])
      .filter(item => item !== id);
    setSuggested(previous => previous.filter(item => item !== id));
    setState(previous => ({
      ...previous,
      requisitesByType: {
        ...previous.requisitesByType,
        [previous.docType]: { ...(previous.requisitesByType[previous.docType] ?? {}), [id]: value },
      },
    }));
    setResult(null);
    setFailure(null);
    setDownloadedName('');
  }

  /** Values the person already wrote in their own draft, put into the empty fields. */
  const fillFromDraft = useCallback(async (typeId: string, quiet = false) => {
    if (!state.draft.trim()) return;
    setSuggestBusy(true);
    try {
      const found = await suggestRequisites(state.draft, typeId);
      if (found === null) {
        setSuggestSupported(false);
        if (!quiet) setToast({ message: 'Этот backend не разбирает черновик на реквизиты.', tone: 'info' });
        return;
      }
      const current = state.requisitesByType[typeId] ?? {};
      const added = Object.entries(found)
        .filter(([id, value]) => value.trim() && !(current[id] ?? '').trim());
      if (!added.length) {
        if (!quiet) setToast({ message: 'В черновике не нашлось подписанных реквизитов.', tone: 'info' });
        return;
      }
      autofilled.current[typeId] = [
        ...(autofilled.current[typeId] ?? []), ...added.map(([id]) => id),
      ];
      setSuggested(added.map(([id]) => id));
      setResult(null);
      setState(previous => ({
        ...previous,
        requisitesByType: {
          ...previous.requisitesByType,
          [typeId]: { ...(previous.requisitesByType[typeId] ?? {}), ...Object.fromEntries(added) },
        },
      }));
    } catch {
      // The hint is optional: without it the form simply stays as the person left it.
    } finally {
      setSuggestBusy(false);
    }
  }, [state.draft, state.requisitesByType]);

  function goOptions() {
    navigate('/options');
    void fillFromDraft(state.docType, true);
  }

  async function prepare() {
    if (!docType || !state.draft.trim() || busy) return;
    if (result) { navigate('/result'); return; }
    setBusy('process');
    setFailure(null);
    try {
      // Only fields of the current type cross the API boundary; other types stay local.
      const selected = Object.fromEntries(
        docType.fields.map(field => [field.id, requisites[field.id] ?? '']),
      );
      const answer = await processDocument(state.draft, state.docType, selected);
      setResult(answer.result);
      setOutcome({ cache: answer.cache, elapsedMs: answer.elapsedMs });
      navigate('/result');
    } catch (error) {
      setFailure(asFailure(error));
    } finally {
      setBusy(null);
    }
  }

  async function download() {
    if (!result || busy) return;
    setBusy('download');
    setFailure(null);
    setDownloadedName('');
    try {
      setDownloadedName(await downloadDocument(result.document, state.templateId));
    } catch (error) {
      setFailure(asFailure(error));
    } finally {
      setBusy(null);
    }
  }

  async function copyText() {
    if (!docType) return;
    const lines = arrangeBlocks(previewContent, docType).flatMap(block => {
      if (block.kind === 'title') return [docType.title];
      if (block.kind === 'body') return previewContent.body;
      return block.items.map(item => block.kind === 'labeled'
        ? `${item.field.label}: ${item.text}` : item.text);
    });
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setToast({ message: 'Текст документа скопирован.', tone: 'success' });
    } catch {
      setToast({ message: 'Браузер не дал доступ к буферу обмена.', tone: 'warn' });
    }
  }

  function startDraft(draft: string, docTypeId: string) {
    changeDraft(draft);
    setState(previous => ({ ...previous, docType: docTypeId }));
    navigate('/draft');
    window.requestAnimationFrame(() => document.getElementById('draft')?.focus());
  }

  /** A filled page for the catalog thumbnails: the person's own values where they exist. */
  const catalogSample = useCallback((typeId: string): DocumentContent => {
    const type = catalog?.doc_types.find(item => item.id === typeId);
    const stored = state.requisitesByType[typeId] ?? {};
    const values: Record<string, string> = {};
    for (const field of type?.fields ?? []) {
      values[field.id] = stored[field.id]?.trim() || DEMO_REQUISITES[field.id] || '';
    }
    const body = splitParagraphs(state.draft || sampleFor(typeId).draft);
    return { doc_type: typeId, requisites: values, body: body.length ? body : EMPTY_PAGE };
  }, [catalog, state.requisitesByType, state.draft]);

  useHotkeys([
    {
      key: 'enter',
      ctrl: true,
      run: () => {
        if (path === '/draft' && state.draft.trim()) goOptions();
        else if (path === '/options') void prepare();
        else if (path === '/result') void download();
        else if (path === '/' || path === '/catalog') navigate('/draft');
      },
    },
    { key: 's', ctrl: true, run: () => { if (result) void download(); } },
  ]);

  const processorMode = result?.processor_mode ?? status?.processor_mode ?? catalog?.processor_mode ?? '';
  const inStudio = STEP_ROUTES.includes(path);
  const loading = !catalog && !catalogFailure;

  const notices = <>
    {catalogFailure && <Callout tone="error" title={catalogFailure.message}
      action={<Button icon={<Refresh size={16} />}
        onClick={() => void reloadCatalog()}>Повторить</Button>}>
      {catalogFailure.hint || 'Запустите backend и повторите загрузку каталога.'}
    </Callout>}

    {busy === 'process' && <Callout tone="info" live="polite"
      title={<span className="waiting-title">
        <Spinner /> Готовим документ{waiting > 2 ? ` · ${waiting} с` : ''}
      </span>}>
      {waiting > 12
        ? 'Модель обрабатывает черновик целиком. Это может занять до двух минут — страница останется здесь.'
        : 'Текст и реквизиты ушли на обработку. Введённые данные остаются в форме.'}
    </Callout>}

    {failure && <Callout tone="error" title={failure.message}
      action={failure.retryable && path === '/options'
        ? <Button icon={<Refresh size={16} />} onClick={() => void prepare()}>Повторить</Button>
        : undefined}>
      {failure.hint}
      {failure.issues.length > 0 && <ul className="issue-list">
        {failure.issues.map(issue => <li key={`${issue.field}-${issue.message}`}>
          <code>{issue.field}</code> — {issue.message}
        </li>)}
      </ul>}
      {failure.requestId && <span className="request-id">Номер запроса: {failure.requestId}</span>}
    </Callout>}
  </>;

  return <div className="app">
    <HeroCanvas theme={theme} muted={path !== '/'} />
    <a className="skip-link" href="#main">Перейти к содержанию</a>
    <Header path={path} reachable={reachable} canGoBack={canGoBack}
      offline={Boolean(catalogFailure)} processorMode={processorMode}
      theme={theme} onTheme={setTheme} onNavigate={navigate} onBack={back} />

    <main id="main">
      {path === '/' && <HomePage hasDraft={Boolean(state.draft.trim())}
        onStart={() => navigate('/draft')}
        onCatalog={() => navigate('/catalog')}
        onSample={() => {
          // A draft already in the form is never replaced silently: the samples live on step 1.
          if (state.draft.trim()) navigate('/draft');
          else startDraft(SAMPLES[0].draft, SAMPLES[0].docType);
        }} />}

      {path === '/catalog' && (catalog
        ? <CatalogPage catalog={catalog} docTypeId={state.docType} templateId={state.templateId}
          sample={catalogSample}
          onPick={typeId => {
            setState(previous => ({ ...previous, docType: typeId }));
            setResult(null);
          }}
          onTemplate={templateId => setState(previous => ({ ...previous, templateId }))}
          onStart={() => navigate('/draft')} />
        : <div className="view view-empty">{notices}
          {loading && <div className="loading-block"><Spinner label="Загрузка каталога…" /></div>}
        </div>)}

      {inStudio && <div className="view view-studio">
        <div className="studio-grid">
          <div className="studio-main">
            {loading && <div className="loading-block"><Spinner label="Загрузка типов документов…" /></div>}

            {catalog && docType && <>
              {path === '/draft' && <DraftStep draft={state.draft} saved={saved} busy={busy !== null}
                onDraft={changeDraft}
                onSample={(draft, typeId) => startDraft(draft, typeId)}
                onNext={goOptions} />}

              {path === '/options' && <OptionsStep catalog={catalog} docType={docType}
                templateId={state.templateId} requisites={requisites}
                suggested={suggested} suggestBusy={suggestBusy} suggestSupported={suggestSupported}
                preview={previewContent} busy={busy !== null}
                onType={typeId => {
                  setState(previous => ({ ...previous, docType: typeId }));
                  setResult(null);
                  setDownloadedName('');
                  setSuggested([]);
                  void fillFromDraft(typeId, true);
                }}
                onTemplate={templateId => setState(previous => ({ ...previous, templateId }))}
                onRequisite={changeRequisite}
                onFocusField={setFocusId}
                onSuggest={() => void fillFromDraft(state.docType)}
                onBack={() => navigate('/draft')}
                onPrepare={() => void prepare()} />}

              {path === '/result' && result && <ReviewStep result={result} docType={docType}
                templates={catalog.templates} templateId={state.templateId} busy={busy !== null}
                cache={outcome.cache} elapsedMs={outcome.elapsedMs} downloadedName={downloadedName}
                onTemplate={templateId => setState(previous => ({ ...previous, templateId }))}
                onDownload={() => void download()}
                onPrint={() => window.print()}
                onCopy={() => void copyText()}
                onBack={() => navigate('/options')} />}
            </>}

            {notices}
          </div>

          {catalog && docType && template && <PreviewPane content={previewContent}
            docType={docType} template={template} prepared={Boolean(result)} focusId={focusId} />}
        </div>
      </div>}
    </main>

    <footer className="app-footer">
      <div className="footer-inner">
        <p className="footer-note">
          Черновик хранится в этом браузере. Обработчик:{' '}
          {processorMode ? processorLabel(processorMode).text.toLowerCase() : 'неизвестен'}.
        </p>
      </div>
    </footer>

    {toast && <Toast message={toast.message} tone={toast.tone} onDone={() => setToast(null)} />}
    <CursorBeam />
  </div>;
}
