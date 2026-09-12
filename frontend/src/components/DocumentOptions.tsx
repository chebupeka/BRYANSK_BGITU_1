import { Alert, Input, Select } from 'antd';
import type { Catalog, DocumentType } from '../types';

interface Props {
  catalog: Catalog;
  type: DocumentType;
  templateId: string;
  requisites: Record<string, string>;
  suggested: string[];
  disabled: boolean;
  onType: (id: string) => void;
  onTemplate: (id: string) => void;
  onRequisite: (id: string, value: string) => void;
}

export default function DocumentOptions(props: Props) {
  const filled = props.type.fields
    .filter(field => props.suggested.includes(field.id))
    .map(field => field.label);
  return <>
    <h2>Выберите документ</h2>
    <label className="field-label" htmlFor="document-type">Тип документа</label>
    <Select id="document-type" value={props.type.id} disabled={props.disabled}
      onChange={props.onType} className="full-width"
      options={props.catalog.doc_types.map(type => ({ value: type.id, label: type.name }))} />
    <p className="helper">{props.type.description}</p>

    <fieldset className="template-fieldset" disabled={props.disabled}>
      <legend>Оформление</legend>
      <div className="template-grid">
        {props.catalog.templates.map(template => <label key={template.id}
          className={`template-choice ${template.id === props.templateId ? 'selected' : ''}`}>
          <input type="radio" name="template" value={template.id}
            checked={template.id === props.templateId}
            onChange={() => props.onTemplate(template.id)} />
          <span><strong>{template.name}</strong><small>{template.description}</small></span>
        </label>)}
      </div>
    </fieldset>
    <p className="helper">Тип определяет структуру и реквизиты. Оформление меняет только внешний вид.</p>

    <h3>Реквизиты</h3>
    <p className="helper">Поля со звёздочкой нужны документу. Их можно пропустить: в файле появятся метки «Заполнить». После правки черновика поля заполняются заново по его тексту.</p>
    {filled.length > 0 && <div role="status"><Alert type="info" showIcon
      title={`Из черновика подставлено: ${filled.join(', ')}. Проверьте значения.`} /></div>}
    <div className="requisites-grid">
      {props.type.fields.map(field => <div key={field.id}>
        <label className="field-label" htmlFor={`field-${field.id}`}>
          {field.label}{field.required && <span aria-label="обязательный реквизит"> *</span>}
        </label>
        <Input id={`field-${field.id}`} value={props.requisites[field.id] ?? ''}
          maxLength={500} disabled={props.disabled}
          onChange={event => props.onRequisite(field.id, event.target.value)} />
      </div>)}
    </div>
  </>;
}
