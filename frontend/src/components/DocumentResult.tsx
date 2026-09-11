import { Alert } from 'antd';
import type { DocumentType, ProcessResult } from '../types';

export default function DocumentResult({ result, type }: { result: ProcessResult; type: DocumentType }) {
  const fields = Object.fromEntries(type.fields.map(field => [field.id, field]));
  return <>
    <h2>Проверьте перед скачиванием</h2>
    <p className="helper">Это просмотр содержания. Шрифт, поля и интервалы выбранного оформления применятся в DOCX.</p>
    {result.warnings.map(warning => <Alert key={warning} type="info" showIcon title={warning} />)}
    {result.missing_fields.length > 0 && <Alert type="warning" showIcon
      title={`Не заполнено: ${result.missing_fields.map(field => field.label).join(', ')}`}
      description="Вернитесь к реквизитам или скачайте документ с метками для заполнения." />}
    <article className="document-preview" aria-label="Содержание документа">
      {type.blocks.map(block => {
        if (block === 'title') return <h3 key={block}>{type.title}</h3>;
        if (block === 'body') return <div key={block} className="document-body">
          {result.document.body.map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        </div>;
        const field = fields[block];
        const value = result.document.requisites[block];
        if (!field || (!value && !field.required)) return null;
        return <p key={block} className={!value ? 'missing-value' : ''}>
          <strong>{field.label}: </strong>{value || `[Заполнить: ${field.label}]`}
        </p>;
      })}
    </article>
  </>;
}
