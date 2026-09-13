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
import {
  arrangeBlocks, formattingForTemplate, missingRequired, splitParagraphs,
} from './lib/layout';
import { DEMO_REQUISITES, SAMPLES, sampleFor } from './lib/samples';
import { useRouter, type Route } from './router';
import {
  loadCustomTemplates, loadDraft, loadTheme, saveCustomTemplates, saveDraft, saveTheme,
} from './storage';
import type {
  ApiFailure, Catalog, DocumentContent, DocumentFormatting, ProcessResult, ServiceStatus, ThemeName,
} from './types';

const EMPTY_PAGE = ['Черновик пока пуст. Начните печатать — страница соберётся здесь.'];
const STEP_ROUTES: Route[] = ['/draft', '/options', '/result'];

function sameParagraphs(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((paragraph, index) => paragraph === right[index]);
}

export default function App() {
  const [state, setState] = useState(loadDraft);
  const [theme, setTheme] = useState<ThemeName>(loadTheme);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogFailure, setCatalogFailure] = useState<ApiFailure | null>(null);
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [formatting, setFormatting] = useState<DocumentFormatting | null>(null);
  const [outcome, setOutcome] = useState({ cache: '', elapsedMs: 0 });
  const [busy, setBusy] = useState<'process' | 'download' | null>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);
  const [downloadedName, setDownloadedName] = useState('');
  const [saved, setSaved] = useState(true);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [suggestedFor, setSuggestedFor] = useState('');
  const [suggestBusy, setSuggestBusy] = useState(false);
  const [focusId, setFocusId] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{ message: string; tone: 'info' | 'success' | 'warn' } | null>(null);
  const [pendingBodyFilled, setPendingBodyFilled] = useState<boolean | null>(null);

  const { path, navigate, back, canGoBack } = useRouter();

  // Which requisites came out of the draft rather than from the keyboard: only these are
  // dropped when the draft changes, so typed values survive an edit of the text.
  const autofilled = useRef<Record<string, string[]>>({});
  // contentEditable owns the live DOM while the user is typing. Keep its newest value
  // outside React state so clicking Download cannot lose the last keystroke on blur.
  const editedDocumentRef = useRef<DocumentContent | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const waiting = useElapsedSeconds(busy === 'process');

  const docType = catalog?.doc_types.find(type => type.id === state.docType);
  const template = catalog?.templates.find(item => item.id === state.templateId);
  const editorFormatting = useMemo(
    () => template ? formatting ?? formattingForTemplate(template) : null,
    [formatting, template],
  );
  const previewTemplate = useMemo(
    () => template && formatting ? { ...template, ...formatting } : template,
    [formatting, template],
  );
  const suggestionKey = `${state.docType}\u0000${docType?.fields.map(field => field.id).join(',') ?? ''}\u0000${state.draft}`;
  const requisites = useMemo(
    () => state.requisitesByType[state.docType] ?? {},
    [state.requisitesByType, state.docType],
  );

  const previewContent: DocumentContent = useMemo(() => {
    if (result) return result.document;
    const body = splitParagraphs(state.draft);
    return {
      doc_type: state.docType,
      requisites,
      // An empty editable sheet uses its own hint instead of turning the hint into document text.
      body: body.length ? body : path === '/draft' ? [] : EMPTY_PAGE,
    };
  }, [result, state.draft, state.docType, requisites, path]);

  const reachable = result ? 2 : state.draft.trim() ? 1 : 0;

  const reloadCatalog = useCallback(async () => {
    setCatalogFailure(null);
    try {
      const next = await getCatalog();
      if (!next.doc_types.length || !next.templates.length) {
        throw new Error('Каталог документов пока пуст. Проверьте конфигурации backend.');
      }
      const remoteIds = new Set(next.templates.map(item => item.id));
      const customTemplates = loadCustomTemplates().filter(item => !remoteIds.has(item.id));
      const fullCatalog = { ...next, templates: [...next.templates, ...customTemplates] };
      setCatalog(fullCatalog);
      void getStatus().then(setStatus);
      setState(previous => ({
        ...previous,
        docType: next.doc_types.some(type => type.id === previous.docType)
          ? previous.docType : next.doc_types[0].id,
        templateId: fullCatalog.templates.some(item => item.id === previous.templateId)
          ? previous.templateId : fullCatalog.templates[0].id,
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
    editedDocumentRef.current = null;
    setPendingBodyFilled(null);
    setSuggested([]);
    setSuggestedFor('');
    setResult(null);
    setFailure(null);
    setDownloadedName('');
  }

  function changeRequisite(id: string, value: string) {
    editedDocumentRef.current = null;
    setPendingBodyFilled(null);
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

  // Requisites are extracted whenever this step opens (including a direct page reload) or
  // its document type changes. While the request is in flight the form waits, so it never
  // flashes fields that are about to be filled and hidden.
  useEffect(() => {
    if (path !== '/options' || !state.draft.trim() || !catalog) {
      setSuggestBusy(false);
      return;
    }

    const typeId = state.docType;
    const type = catalog.doc_types.find(item => item.id === typeId);
    if (!type) {
      setSuggestBusy(false);
      return;
    }
    const requestKey = `${typeId}\u0000${type.fields.map(field => field.id).join(',')}\u0000${state.draft}`;
    if (suggestedFor === requestKey) {
      setSuggestBusy(false);
      return;
    }

    let active = true;
    setSuggested([]);
    setSuggestBusy(true);
    setFocusId(undefined);

    void suggestRequisites(state.draft, typeId).then(found => {
      if (!active || found === null) return;
      const fieldIds = new Set(type.fields.map(field => field.id));
      const parsed = Object.entries(found)
        .filter(([id, value]) => fieldIds.has(id) && value.trim());
      setSuggested(parsed.map(([id]) => id));

      const current = stateRef.current.requisitesByType[typeId] ?? {};
      const added = parsed.filter(([id]) => !(current[id] ?? '').trim());
      if (!added.length) return;

      autofilled.current[typeId] = [
        ...new Set([...(autofilled.current[typeId] ?? []), ...added.map(([id]) => id)]),
      ];
      setResult(null);
      setState(previous => {
        const fields = { ...(previous.requisitesByType[typeId] ?? {}) };
        let changed = false;
        for (const [id, value] of added) {
          if ((fields[id] ?? '').trim()) continue;
          fields[id] = value;
          changed = true;
        }
        if (!changed) return previous;
        return {
          ...previous,
          requisitesByType: { ...previous.requisitesByType, [typeId]: fields },
        };
      });
    }).catch(() => {
      // If automatic extraction is unavailable, every field remains visible for manual input.
    }).finally(() => {
      if (active) {
        setSuggestedFor(requestKey);
        setSuggestBusy(false);
      }
    });

    return () => { active = false; };
  }, [catalog, path, state.docType, state.draft, suggestedFor]);

  function goOptions() {
    const pending = editedDocumentRef.current;
    if (pending && path === '/draft') editPreviewDocument(pending);
    const hasBody = pending?.body.some(paragraph => paragraph.trim()) ?? Boolean(state.draft.trim());
    if (!hasBody) return;
    navigate('/options');
  }

  async function prepare() {
    const pending = path === '/options' ? editedDocumentRef.current : null;
    const draft = pending ? pending.body.join('\n\n') : state.draft;
    const activeRequisites = pending?.requisites ?? requisites;
    const draftChangedOnSheet = Boolean(
      pending && !sameParagraphs(pending.body, splitParagraphs(state.draft)),
    );
    if (!docType || !draft.trim() || busy || suggestBusy
      || (!draftChangedOnSheet && suggestedFor !== suggestionKey)) return;
    if (pending) editPreviewDocument(pending);
    if (result && !pending) { navigate('/result'); return; }
    setBusy('process');
    setFailure(null);
    try {
      // Only fields of the current type cross the API boundary; other types stay local.
      const selected = Object.fromEntries(
        docType.fields.map(field => [field.id, activeRequisites[field.id] ?? '']),
      );
      const answer = await processDocument(draft, state.docType, selected);
      editedDocumentRef.current = null;
      setPendingBodyFilled(null);
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
    if (!result || !template || busy) return;
    const document = editedDocumentRef.current ?? result.document;
    if (!document.body.some(paragraph => paragraph.trim())) {
      editDocument(document);
      return;
    }
    if (editedDocumentRef.current) syncEditedDocument(document);
    setBusy('download');
    setFailure(null);
    setDownloadedName('');
    try {
      setDownloadedName(await downloadDocument(
        document, template, formatting ?? undefined,
      ));
    } catch (error) {
      setFailure(asFailure(error));
    } finally {
      setBusy(null);
    }
  }

  async function copyText() {
    if (!docType) return;
    const document = editedDocumentRef.current ?? previewContent;
    const lines = arrangeBlocks(document, docType).flatMap(block => {
      if (block.kind === 'title') return [docType.title];
      if (block.kind === 'body') return document.body;
      return block.items.map(item => block.kind === 'labeled'
        ? `${item.field.label}: ${item.text}` : item.text);
    });
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      if (editedDocumentRef.current) syncEditedDocument(document);
      setToast({ message: 'Текст документа скопирован.', tone: 'success' });
    } catch {
      setToast({ message: 'Браузер не дал доступ к буферу обмена.', tone: 'warn' });
    }
  }

  function syncEditedDocument(document: DocumentContent) {
    setResult(previous => previous ? {
      ...previous,
      document,
      missing_fields: docType ? missingRequired(document, docType) : previous.missing_fields,
    } : previous);
  }

  function draftDocument(document: DocumentContent) {
    editedDocumentRef.current = document;
    if (path !== '/result') {
      const filled = document.body.some(paragraph => paragraph.trim());
      setPendingBodyFilled(previous => previous === filled ? previous : filled);
    }
  }

  function editPreviewDocument(document: DocumentContent) {
    if (path === '/result') {
      editDocument(document);
      return;
    }
    const nextDraft = document.body.join('\n\n');
    if (!sameParagraphs(document.body, splitParagraphs(state.draft))) {
      changeDraft(nextDraft);
      return;
    }
    const changed = docType?.fields.find(
      field => (document.requisites[field.id] ?? '') !== (requisites[field.id] ?? ''),
    );
    if (changed) changeRequisite(changed.id, document.requisites[changed.id] ?? '');
    else {
      editedDocumentRef.current = null;
      setPendingBodyFilled(null);
    }
  }

  function editDocument(document: DocumentContent) {
    editedDocumentRef.current = document;
    syncEditedDocument(document);
    setDownloadedName('');
    setFailure(null);
  }

  function changeResultTemplate(templateId: string) {
    setState(previous => ({ ...previous, templateId }));
    setFormatting(null);
    setDownloadedName('');
  }

  function changeFormatting(next: DocumentFormatting | null) {
    setFormatting(next);
    setDownloadedName('');
    setFailure(null);
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
        if (path === '/draft') goOptions();
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
            editedDocumentRef.current = null;
            setState(previous => ({ ...previous, docType: typeId }));
            setResult(null);
            setFormatting(null);
          }}
          onTemplate={templateId => {
            setState(previous => ({ ...previous, templateId }));
            setFormatting(null);
          }}
          onCreateTemplate={created => {
            setCatalog(previous => {
              if (!previous) return previous;
              const custom = [
                ...previous.templates.filter(item => item.id.startsWith('custom_')),
                created,
              ];
              saveCustomTemplates(custom);
              return { ...previous, templates: [...previous.templates, created] };
            });
            setState(previous => ({ ...previous, templateId: created.id }));
            setResult(null);
            setToast({ message: `Оформление «${created.name}» сохранено.`, tone: 'success' });
          }}
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
                canContinue={pendingBodyFilled ?? Boolean(state.draft.trim())}
                onDraft={changeDraft}
                onSample={(draft, typeId) => startDraft(draft, typeId)}
                onNext={goOptions} />}

              {path === '/options' && <OptionsStep catalog={catalog} docType={docType}
                templateId={state.templateId} requisites={requisites}
                suggested={suggested}
                suggestBusy={suggestBusy || suggestedFor !== suggestionKey}
                preview={previewContent} busy={busy !== null}
                onType={typeId => {
                  editedDocumentRef.current = null;
                  setState(previous => ({ ...previous, docType: typeId }));
                  setResult(null);
                  setFormatting(null);
                  setDownloadedName('');
                  setSuggested([]);
                  setSuggestedFor('');
                }}
                onTemplate={changeResultTemplate}
                onRequisite={changeRequisite}
                onFocusField={setFocusId}
                onBack={() => {
                  const pending = editedDocumentRef.current;
                  if (pending) editPreviewDocument(pending);
                  navigate('/draft');
                }}
                onPrepare={() => void prepare()} />}

              {path === '/result' && result && <ReviewStep result={result} docType={docType}
                busy={busy !== null}
                canDownload={result.document.body.some(paragraph => paragraph.trim())}
                cache={outcome.cache} elapsedMs={outcome.elapsedMs} downloadedName={downloadedName}
                onDownload={() => void download()}
                onPrint={() => {
                  const document = editedDocumentRef.current;
                  if (document) syncEditedDocument(document);
                  window.print();
                }}
                onCopy={() => void copyText()}
                onBack={() => {
                  const document = editedDocumentRef.current;
                  if (document) editDocument(document);
                  navigate('/options');
                }} />}
            </>}

            {notices}
          </div>

          {catalog && docType && previewTemplate && editorFormatting && <PreviewPane content={previewContent}
            docType={docType} template={previewTemplate} prepared={Boolean(result)} focusId={focusId}
            templates={catalog.templates}
            formatting={editorFormatting} formattingCustomized={formatting !== null}
            disabled={busy !== null}
            onContentDraftChange={draftDocument}
            onContentChange={editPreviewDocument}
            onTemplate={changeResultTemplate}
            onFormattingChange={changeFormatting}
            onFocusField={setFocusId} />}
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
