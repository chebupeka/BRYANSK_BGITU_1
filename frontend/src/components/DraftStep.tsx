import { useRef, useState } from 'react';
import { AutoTextarea, Button, Callout } from './ui';
import { ArrowRight, Sparkle, Upload } from './icons';
import { SAMPLES } from '../lib/samples';
import { splitParagraphs } from '../lib/layout';

const LIMIT = 20_000;

interface Props {
  draft: string;
  saved: boolean;
  busy: boolean;
  onDraft: (draft: string) => void;
  onSample: (draft: string, docType: string) => void;
  onNext: () => void;
}

function words(text: string): number {
  return (text.match(/[^\s]+/g) ?? []).length;
}

export default function DraftStep({ draft, saved, busy, onDraft, onSample, onNext }: Props) {
  const [dragging, setDragging] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [fileError, setFileError] = useState('');
  const textarea = useRef<HTMLTextAreaElement>(null);

  async function readFile(file: File) {
    setFileError('');
    if (!/\.(txt|md)$/i.test(file.name) && !file.type.startsWith('text/')) {
      setFileError('Подойдёт текстовый файл: .txt или .md. Из Word скопируйте текст вручную.');
      return;
    }
    const text = (await file.text()).slice(0, LIMIT);
    onDraft(text);
    textarea.current?.focus();
  }

  const paragraphs = splitParagraphs(draft).length;
  const nearLimit = draft.length > LIMIT * 0.9;

  return <section className="step-panel" aria-labelledby="step-draft-title">
    <div className="step-head">
      <div>
        <p className="step-mark">Шаг 1</p>
        <h2 id="step-draft-title">Черновик</h2>
        <p className="step-lead">Пишите свободно: даты, суммы и имена останутся как есть.</p>
      </div>
    </div>

    <div className="sample-row">
      <span className="sample-label"><Sparkle size={16} /> Примеры</span>
      <div className="sample-chips">
        {SAMPLES.map(sample => <button key={sample.id} type="button" className="chip"
          title={sample.note} disabled={busy}
          onClick={() => onSample(sample.draft, sample.docType)}>{sample.name}</button>)}
      </div>
    </div>

    <div className={`draft-box ${dragging ? 'is-dragging' : ''}`}
      onDragOver={event => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={event => {
        event.preventDefault();
        setDragging(false);
        const file = event.dataTransfer.files[0];
        if (file) void readFile(file);
      }}>
      <AutoTextarea ref={textarea} id="draft" value={draft} maxLength={LIMIT}
        spellCheck lang="ru" disabled={busy}
        aria-label="Черновик документа"
        placeholder={'Например:\nПрошу согласовать закупку двух мониторов для учебной аудитории.\nСтоимость — 30 000 рублей, поставка до 25.09.2026.'}
        onChange={event => onDraft(event.target.value)} />
      <div className="draft-drop" aria-hidden="true">
        <Upload size={22} />
        <span>Отпустите файл .txt — текст попадёт в черновик</span>
      </div>
    </div>

    <div className="draft-meta">
      <span className={saved ? 'meta-ok' : 'meta-warn'}>
        {saved ? 'Черновик сохраняется в этом браузере' : 'Автосохранение недоступно'}
      </span>
      <span className="meta-counts">
        {paragraphs} абз. · {words(draft)} слов
        <span className={nearLimit ? 'meta-warn' : ''}>
          {' · '}{draft.length.toLocaleString('ru-RU')} / {LIMIT.toLocaleString('ru-RU')}
        </span>
      </span>
    </div>

    {!saved && <Callout tone="warn" title="Браузер не разрешил сохранить черновик">
      Скопируйте текст перед закрытием страницы: после перезагрузки он не восстановится.
    </Callout>}
    {fileError && <Callout tone="warn" title={fileError} />}

    <div className="step-actions">
      <Button variant="primary" size="lg" disabled={!draft.trim() || busy}
        iconRight={<ArrowRight size={18} />} onClick={onNext}>
        Выбрать тип документа
      </Button>
      {draft && <Button variant="quiet" onClick={() => {
        if (!confirmClear) { setConfirmClear(true); return; }
        onDraft('');
        setConfirmClear(false);
        textarea.current?.focus();
      }} onBlur={() => setConfirmClear(false)}>
        {confirmClear ? 'Точно очистить?' : 'Очистить'}
      </Button>}
      <span className="hotkey-hint">Ctrl + Enter — дальше</span>
    </div>
  </section>;
}
