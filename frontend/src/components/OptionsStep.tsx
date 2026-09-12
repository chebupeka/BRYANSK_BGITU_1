import { Button, Callout, Field } from './ui';
import { ArrowLeft, ArrowRight, Check, Sparkle } from './icons';
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
  suggestSupported: boolean;
  preview: DocumentContent;
  busy: boolean;
  onType: (id: string) => void;
  onTemplate: (id: string) => void;
  onRequisite: (id: string, value: string) => void;
  onFocusField: (id: string | undefined) => void;
  onSuggest: () => void;
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

    <div className="group-title-row">
      <h3 className="group-title">Реквизиты</h3>
      {props.suggestSupported && <Button variant="quiet" size="md" loading={props.suggestBusy}
        icon={<Sparkle size={16} />} onClick={props.onSuggest} disabled={props.busy}>
        Заполнить из черновика
      </Button>}
    </div>
    <p className="group-hint">
      Поля со звёздочкой можно пропустить: на их месте появятся метки «Заполнить».
    </p>

    {props.suggested.length > 0 && <Callout tone="info" live="polite"
      title={`Из черновика: ${docType.fields
        .filter(field => props.suggested.includes(field.id))
        .map(field => field.label).join(', ')}. Проверьте значения.`} />}

    <div className="requisites-grid">
      {docType.fields.map(field => <Field key={field.id} id={`field-${field.id}`}
        label={field.label} required={field.required} hint={hintFor(field)}
        highlight={props.suggested.includes(field.id)}>
        <input id={`field-${field.id}`} className="input" type="text" maxLength={500}
          value={requisites[field.id] ?? ''} disabled={props.busy}
          autoComplete="off" spellCheck
          onFocus={() => props.onFocusField(field.id)}
          onBlur={() => props.onFocusField(undefined)}
          onChange={event => props.onRequisite(field.id, event.target.value)} />
      </Field>)}
    </div>

    {missing.length > 0 && <Callout tone="warn"
      title={`Не заполнено: ${missing.map(field => field.label).join(', ')}`}>
      Можно продолжить — в документе останутся метки.
    </Callout>}

    <div className="step-actions">
      <Button variant="quiet" icon={<ArrowLeft size={18} />} onClick={props.onBack}
        disabled={props.busy}>К черновику</Button>
      <Button variant="primary" size="lg" loading={props.busy}
        iconRight={<ArrowRight size={18} />} onClick={props.onPrepare}>
        Подготовить документ
      </Button>
      <span className="hotkey-hint">Ctrl + Enter — подготовить</span>
    </div>
  </section>;
}
