import { useState } from 'react';
import { Badge, Button, Callout } from './ui';
import { ArrowLeft, Check, Copy, Download, Print } from './icons';
import type { DocumentType, ProcessResult } from '../types';

interface Props {
  result: ProcessResult;
  docType: DocumentType;
  busy: boolean;
  canDownload: boolean;
  cache: string;
  elapsedMs: number;
  downloadedName: string;
  onDownload: () => void;
  onPrint: () => void;
  onCopy: () => void;
  onBack: () => void;
}

function seconds(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} с` : `${Math.round(ms)} мс`;
}

export default function ReviewStep(props: Props) {
  const { result } = props;
  const [showChanges, setShowChanges] = useState(true);

  return <section className="step-panel" aria-labelledby="step-result-title">
    <div className="step-head">
      <div>
        <p className="step-mark">Шаг 3</p>
        <h2 id="step-result-title">Готовый файл</h2>
        <p className="step-lead">Справа можно проверить лист, поправить текст или сменить оформление перед скачиванием.</p>
      </div>
      <div className="result-stamps">
        {props.cache === 'HIT' && <Badge tone="neutral"
          title="Тот же черновик уже обрабатывали: ответ взят из кэша backend.">Из кэша</Badge>}
        {props.elapsedMs > 0 && <Badge tone="neutral"
          title="Время ответа backend на подготовку.">{seconds(props.elapsedMs)}</Badge>}
      </div>
    </div>

    {result.warnings.map(warning => <Callout key={warning} tone="info" title={warning} />)}

    {result.missing_fields.length > 0 && <Callout tone="warn"
      title={`Остались пустыми: ${result.missing_fields.map(field => field.label).join(', ')}`}
      action={<Button variant="quiet" onClick={props.onBack}>Заполнить</Button>} />}

    {result.changes.length > 0 && <div className="changes">
      <button type="button" className="changes-toggle" aria-expanded={showChanges}
        onClick={() => setShowChanges(!showChanges)}>
        <Check size={16} /> Что изменил обработчик · {result.changes.length}
      </button>
      {showChanges && <ul className="changes-list">
        {result.changes.map((change, index) => <li key={index}>{change}</li>)}
      </ul>}
    </div>}

    {!props.canDownload && <Callout tone="warn"
      title="Основной текст документа пуст">
      Откройте режим «Текст» справа и добавьте хотя бы один абзац.
    </Callout>}

    {props.downloadedName && <Callout tone="success" live="polite"
      title={`Файл ${props.downloadedName} передан браузеру`} />}

    <div className="step-actions">
      <Button variant="quiet" icon={<ArrowLeft size={18} />} onClick={props.onBack}
        data-document-action="back" disabled={props.busy}>К реквизитам</Button>
      <Button variant="primary" size="lg" loading={props.busy} icon={<Download size={18} />}
        data-document-action="download" disabled={!props.canDownload}
        onClick={props.onDownload}>Скачать DOCX</Button>
      <Button variant="quiet" icon={<Print size={18} />} onClick={props.onPrint}
        data-document-action="print" disabled={props.busy}>Печать</Button>
      <Button variant="quiet" icon={<Copy size={18} />} onClick={props.onCopy}
        data-document-action="copy" disabled={props.busy}>Скопировать текст</Button>
      <span className="hotkey-hint">Ctrl + S — скачать</span>
    </div>
  </section>;
}
