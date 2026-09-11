import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Input, Spin, Steps } from 'antd';
import { downloadDocument, getCatalog, processDocument, suggestRequisites } from './api';
import DocumentOptions from './components/DocumentOptions';
import DocumentResult from './components/DocumentResult';
import { loadDraft, saveDraft } from './storage';
import type { Catalog, DraftState, ProcessResult } from './types';

const DEMO = 'Прошу согласовать закупку двух мониторов для учебной аудитории.\nСтоимость — 30 000 рублей. Поставка нужна до 25.09.2026 при условии согласования бюджета.';

export default function App() {
  const [state, setState] = useState<DraftState>(loadDraft);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState('');
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [downloaded, setDownloaded] = useState(false);
  const [saved, setSaved] = useState(true);
  const [suggested, setSuggested] = useState<string[]>([]);
  const mainRef = useRef<HTMLElement>(null);
  const docType = catalog?.doc_types.find(type => type.id === state.docType);
  const template = catalog?.templates.find(item => item.id === state.templateId);
  const requisites = state.requisitesByType[state.docType] ?? {};

  async function reloadCatalog() {
    setCatalogError('');
    try {
      const next = await getCatalog();
      if (!next.doc_types.length || !next.templates.length) throw new Error('Каталог документов пока пуст.');
      setCatalog(next);
      setState(previous => ({ ...previous,
        docType: next.doc_types.some(type => type.id === previous.docType) ? previous.docType : next.doc_types[0].id,
        templateId: next.templates.some(item => item.id === previous.templateId) ? previous.templateId : next.templates[0].id,
      }));
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : 'Не удалось загрузить каталог.');
    }
  }

  useEffect(() => { void reloadCatalog(); }, []);
  useEffect(() => { setSaved(saveDraft(state)); }, [state]);
  useEffect(() => { mainRef.current?.focus(); }, [step]);

  function update(patch: Partial<DraftState>, changesContent = true) {
    setState(previous => ({ ...previous, ...patch }));
    if (changesContent) setResult(null);
    setError('');
    setDownloaded(false);
  }

  // Подставляет в пустые поля то, что пользователь сам подписал в черновике.
  async function fillFromDraft(typeId: string) {
    setSuggested([]);
    if (!state.draft.trim()) return;
    try {
      const found = await suggestRequisites(state.draft, typeId);
      const current = state.requisitesByType[typeId] ?? {};
      const added = Object.entries(found)
        .filter(([id, value]) => value && !(current[id] ?? '').trim());
      if (!added.length) return;
      setSuggested(added.map(([id]) => id));
      setResult(null);
      setState(previous => ({ ...previous, requisitesByType: {
        ...previous.requisitesByType,
        [typeId]: { ...(previous.requisitesByType[typeId] ?? {}), ...Object.fromEntries(added) },
      } }));
    } catch {
      // Подсказка необязательна: без неё форма просто остаётся пустой.
    }
  }

  async function prepare() {
    if (!docType || !state.draft.trim()) return;
    if (result) { setStep(2); return; }
    setBusy(true);
    setError('');
    try {
      // Only current type fields cross the API boundary; other type drafts stay local.
      const selected = Object.fromEntries(docType.fields.map(field => [field.id, requisites[field.id] ?? '']));
      setResult(await processDocument(state.draft, state.docType, selected));
      setStep(2);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось подготовить документ.');
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    if (!result) return;
    setBusy(true);
    setError('');
    setDownloaded(false);
    try {
      await downloadDocument(result.document, state.templateId);
      setDownloaded(true);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось скачать файл.');
    } finally {
      setBusy(false);
    }
  }

  return <div className="app-shell">
    <header className="app-header">
      <a className="brand" href="/" aria-label="Документ за 3 шага — главная">
        <img src="/favicon.svg" alt="" width="34" height="34" />
        <span>Документ <strong>за 3 шага</strong></span>
      </a>
      <span className="version-label">Демо · 0.1</span>
    </header>

    <div className="page-intro">
      <p className="eyebrow">ОТ ЧЕРНОВИКА К ДОКУМЕНТУ</p>
      <h1>Подготовьте документ</h1>
      <p>Введите текст, выберите оформление и скачайте файл для редактирования в Word.</p>
    </div>

    <Steps current={step} responsive items={[
      { title: 'Черновик' }, { title: 'Тип и реквизиты' }, { title: 'Готовый файл' },
    ]} />

    <div className="workspace">
      <main className="editor-panel" ref={mainRef} tabIndex={-1}>
        {step === 0 && <>
          <div className="section-title"><h2>С чего начнём?</h2>
            <Button type="link" disabled={busy || !!state.draft} onClick={() => update({ draft: DEMO })}>
              Вставить пример
            </Button>
          </div>
          <label className="field-label" htmlFor="draft">Черновик документа</label>
          <Input.TextArea id="draft" value={state.draft} maxLength={20_000}
            placeholder="Напишите или вставьте текст. Сохраните в нём известные даты, имена, суммы и условия."
            autoSize={{ minRows: 10, maxRows: 22 }}
            onChange={event => update({ draft: event.target.value })} />
          <div className="draft-meta"><span>{saved ? 'Черновик сохраняется в этом браузере' : 'Автосохранение недоступно'}</span>
            <span>{state.draft.length.toLocaleString('ru-RU')} / 20 000</span></div>
          {!saved && <Alert type="warning" showIcon title="Браузер не разрешил сохранить данные. Скопируйте текст перед закрытием страницы." />}
        </>}

        {step === 1 && catalog && docType && <DocumentOptions catalog={catalog} type={docType}
          templateId={state.templateId} requisites={requisites} disabled={busy}
          suggested={suggested}
          onType={nextType => { update({ docType: nextType }); void fillFromDraft(nextType); }}
          onTemplate={templateId => update({ templateId }, false)}
          onRequisite={(id, value) => update({ requisitesByType: {
            ...state.requisitesByType, [state.docType]: { ...requisites, [id]: value },
          } })} />}

        {step === 2 && result && docType && <DocumentResult result={result} type={docType} />}
        {catalogError && <Alert type="error" showIcon title={catalogError}
          action={<Button onClick={() => void reloadCatalog()}>Повторить</Button>} />}
        {!catalog && !catalogError && <div className="loading"><Spin size="small" /> Загрузка типов документов…</div>}
        {error && <div role="alert"><Alert type="error" showIcon title={error} /></div>}
        {downloaded && <div role="status"><Alert type="success" showIcon title="Файл передан браузеру для скачивания. Текст в DOCX можно редактировать." /></div>}

        <div className="actions">
          {step > 0 && <Button disabled={busy} onClick={() => { setStep(step - 1); setError(''); }}>
            {step === 2 ? 'К реквизитам' : 'Назад'}
          </Button>}
          {step === 0 && <Button type="primary" disabled={!state.draft.trim() || !docType || !template}
            onClick={() => { setStep(1); void fillFromDraft(state.docType); }}>
            Выбрать тип документа</Button>}
          {step === 1 && <Button type="primary" loading={busy} onClick={() => void prepare()}>
            {error ? 'Повторить подготовку' : 'Подготовить документ'}
          </Button>}
          {step === 2 && <Button type="primary" loading={busy} onClick={() => void download()}>
            Скачать DOCX
          </Button>}
        </div>
      </main>

      <aside className="summary-panel" aria-label="Параметры документа">
        <p className="eyebrow">ВАШ ДОКУМЕНТ</p>
        <h2>{docType?.name ?? 'Новый документ'}</h2>
        <dl><dt>Оформление</dt><dd>{template?.name ?? 'Загружается…'}</dd>
          <dt>Формат файла</dt><dd>DOCX · редактируемый текст</dd></dl>
        {catalog?.processor_mode === 'llm'
          ? <div className="aside-note"><strong>Текст обрабатывает модель</strong>
            <p>Орфография и деловой стиль исправляются локальной моделью. Даты, суммы и имена берутся только из черновика; неподтверждённые реквизиты остаются пустыми. Проверьте результат перед отправкой.</p>
          </div>
          : <div className="aside-note"><strong>Текст без изменений</strong>
            <p>В этой демоверсии текст переносится без исправлений. Автоматическая проверка орфографии и делового стиля пока не подключена.</p>
          </div>}
        <p className="privacy-note">Черновик и реквизиты сохраняются в браузере. Текст отправляется серверу при подготовке и скачивании.</p>
      </aside>
    </div>
    <footer className="app-footer">Документ за 3 шага <span>Проверьте содержание и реквизиты перед использованием.</span></footer>
  </div>;
}
