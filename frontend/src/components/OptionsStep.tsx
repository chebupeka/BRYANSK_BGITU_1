import { Button, Callout, Field, Spinner } from './ui';
import { ArrowLeft, ArrowRight, Check } from './icons';
import PagePreview from './PagePreview';
import type { Catalog, DocumentContent, DocumentType, RequisiteField } from '../types';

interface Props {
  catalog: Catalog;
  docType: DocumentType;
  templateId: string;
  requisites: Record<string, string>;
  /** Requisite ids that were read out of the draft, not typed by hand. */
  suggested: string[];
  suggestBusy: boolean;
  preview: DocumentContent;
  busy: boolean;
  onType: (id: string) => void;
  onTemplate: (id: string) => void;
  onRequisite: (id: string, value: string) => void;
  onFocusField: (id: string | undefined) => void;
  onBack: () => void;
  onPrepare: () => void;
}

function hintFor(field: RequisiteField): string | undefined {
  if (field.summary) return 'Формулируется по смыслу черновика';
  if (field.id === 'date') return 'Например: 12.03.2025';
  if (field.id === 'number') return 'Регистрационный номер, если он уже присвоен';
  return undefined;
}

export default function OptionsStep(props: Props) {
  const { catalog, docType, requisites } = props;
  const missing = docType.fields.filter(
    field => field.required && !(requisites[field.id] ?? '').trim(),
  );
  const unresolved = docType.fields.filter(field => !props.suggested.includes(field.id));
  const parsedLabels = docType.fields
    .filter(field => props.suggested.includes(field.id))
    .map(field => field.label);

  return <section className="step-panel" aria-labelledby="step-options-title">
    <div className="step-head">
      <div>
        <p className="step-mark">Шаг 2</p>
        <h2 id="step-options-title">Тип и реквизиты</h2>
        <p className="step-lead">Тип задаёт структуру, оформление — только внешний вид.</p>
      </div>
    </div>

    <h3 className="group-title">Тип документа</h3>
    <div className="type-grid" role="radiogroup" aria-label="Тип документа">
      {catalog.doc_types.map(type => <button key={type.id} type="button" role="radio"
        aria-checked={type.id === docType.id} disabled={props.busy}
        className={`type-card ${type.id === docType.id ? 'is-selected' : ''}`}
        onClick={() => props.onType(type.id)}>
        <span className="type-card-top">
          <strong>{type.name}</strong>
          <span className="type-check" aria-hidden="true"><Check size={14} /></span>
        </span>
        <span className="type-card-text">{type.description}</span>
        <span className="type-card-fields">
          {type.fields.length} реквизитов · {type.fields.filter(field => field.required).length} обязательных
        </span>
      </button>)}
    </div>

    <h3 className="group-title">Оформление</h3>
    <div className="template-grid" role="radiogroup" aria-label="Оформление">
      {catalog.templates.map(template => <button key={template.id} type="button" role="radio"
        aria-checked={template.id === props.templateId} disabled={props.busy}
        className={`template-card ${template.id === props.templateId ? 'is-selected' : ''}`}
        onClick={() => props.onTemplate(template.id)}>
        <span className="template-thumb" aria-hidden="true">
          <PagePreview content={props.preview} docType={docType} template={template} width={128} />
        </span>
        <span className="template-text">
          <strong>{template.name}</strong>
          <small>{template.description}</small>
          <small className="template-meta">{template.font} · {template.font_size} пт</small>
        </span>
      </button>)}
    </div>

    <h3 className="group-title">Реквизиты</h3>
    <p className="group-hint">
      Показываем только то, чего не удалось найти в черновике. Поля со звёздочкой можно
      пропустить: на их месте появятся метки «Заполнить».
    </p>

    {props.suggestBusy && <div className="loading-block">
      <Spinner label="Ищем реквизиты в черновике…" />
    </div>}

    {!props.suggestBusy && parsedLabels.length > 0 && <Callout
      tone={unresolved.length > 0 ? 'info' : 'success'} live="polite"
      title={unresolved.length > 0
        ? `Найдено в черновике: ${parsedLabels.join(', ')}`
        : 'Все реквизиты заполнены автоматически из черновика.'} />}

    {!props.suggestBusy && unresolved.length > 0 && <div className="requisites-grid">
      {unresolved.map(field => <Field key={field.id} id={`field-${field.id}`}
        label={field.label} required={field.required} hint={hintFor(field)}>
        <input id={`field-${field.id}`} className="input" type="text" maxLength={500}
          value={requisites[field.id] ?? ''} disabled={props.busy}
          autoComplete="off" spellCheck
          onFocus={() => props.onFocusField(field.id)}
          onBlur={() => props.onFocusField(undefined)}
          onChange={event => props.onRequisite(field.id, event.target.value)} />
      </Field>)}
    </div>}

    {!props.suggestBusy && missing.length > 0 && <Callout tone="warn"
      title={`Не заполнено: ${missing.map(field => field.label).join(', ')}`}>
      Можно продолжить — в документе останутся метки.
    </Callout>}

    <div className="step-actions">
      <Button variant="quiet" icon={<ArrowLeft size={18} />} onClick={props.onBack}
        data-document-action="back" disabled={props.busy}>К черновику</Button>
      <Button variant="primary" size="lg" loading={props.busy}
        data-document-action="prepare"
        iconRight={<ArrowRight size={18} />} onClick={props.onPrepare}
        disabled={props.suggestBusy}>
        Подготовить документ
      </Button>
      <span className="hotkey-hint">Ctrl + Enter — подготовить</span>
    </div>
  </section>;
}
