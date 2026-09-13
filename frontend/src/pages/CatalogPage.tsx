import { useState } from 'react';
import PagePreview from '../components/PagePreview';
import TemplateEditor from '../components/TemplateEditor';
import { Button } from '../components/ui';
import { ArrowRight, Check, Sparkle } from '../components/icons';
import { resolveTemplate } from '../lib/layout';
import { useReveal } from '../lib/hooks';
import type { Catalog, DocumentContent, Template } from '../types';

interface Props {
  catalog: Catalog;
  docTypeId: string;
  templateId: string;
  /** A filled sample, so every thumbnail shows a page with text on it. */
  sample: (docTypeId: string) => DocumentContent;
  onPick: (docTypeId: string) => void;
  onTemplate: (templateId: string) => void;
  onCreateTemplate: (template: Template) => void;
  onStart: () => void;
}

function templateFacts(template: Template): string[] {
  const style = resolveTemplate(template);
  const margins = style.margins;
  return [
    `${style.font} · ${style.fontSize} пт`,
    `интервал ${style.lineSpacing.toString().replace('.', ',')}`,
    `поля ${margins.top}/${margins.right}/${margins.bottom}/${margins.left} мм`,
    style.recipientLayout === 'table' ? 'адресат таблицей' : 'адресат блоком',
  ];
}

export default function CatalogPage(props: Props) {
  const reveal = useReveal<HTMLElement>();
  const [editorOpen, setEditorOpen] = useState(false);
  const selectedTemplate = props.catalog.templates.find(item => item.id === props.templateId)
    ?? props.catalog.templates[0];
  const selectedType = props.catalog.doc_types.find(item => item.id === props.docTypeId)
    ?? props.catalog.doc_types[0];

  return <div className="view view-catalog">
    <header className="view-head">
      <p className="eyebrow">Каталог</p>
      <h1>Что можно собрать</h1>
      <p className="view-lead">Выберите письмо, записку или справку. Затем добавьте текст и настройте оформление.</p>
    </header>

    <section className="catalog-section">
      <div className="group-title-row catalog-title-row">
        <h2 className="group-title">Типы документов</h2>
        <Button variant="secondary" icon={<Sparkle size={17} />}
          onClick={() => setEditorOpen(true)}>Создать оформление</Button>
      </div>
      <div className="catalog-grid">
        {props.catalog.doc_types.map(type => {
          const selected = type.id === props.docTypeId;
          return <article key={type.id} className={`catalog-card ${selected ? 'is-selected' : ''}`}>
            <div className="catalog-thumb" aria-hidden="true">
              <PagePreview content={props.sample(type.id)} docType={type}
                template={selectedTemplate} width={176} />
            </div>
            <div className="catalog-text">
              <h3>{type.name} {selected && <span className="catalog-mark"><Check size={14} /></span>}</h3>
              <p>{type.description}</p>
              <ul className="catalog-fields">
                {type.fields.map(field => <li key={field.id}
                  className={field.required ? 'is-required' : ''}>{field.label}</li>)}
              </ul>
              <Button variant={selected ? 'primary' : 'secondary'}
                iconRight={<ArrowRight size={16} />}
                onClick={() => { props.onPick(type.id); props.onStart(); }}>
                {selected ? 'Продолжить' : 'Выбрать тип'}
              </Button>
            </div>
          </article>;
        })}
      </div>
    </section>

    <section className="catalog-section reveal" ref={reveal}>
      <h2 className="group-title">Оформления</h2>
      <p className="group-hint">Оформление не меняет ни одного слова.</p>
      <div className="template-gallery">
        {props.catalog.templates.map(template => {
          const selected = template.id === props.templateId;
          return <article key={template.id}
            className={`gallery-card ${selected ? 'is-selected' : ''}`}>
            <div className="gallery-thumb" aria-hidden="true">
              <PagePreview content={props.sample(selectedType.id)} docType={selectedType}
                template={template} width={248} />
            </div>
            <div className="gallery-text">
              <h3>{template.name}</h3>
              <p>{template.description}</p>
              <ul className="gallery-facts">
                {templateFacts(template).map(fact => <li key={fact}>{fact}</li>)}
              </ul>
              <Button variant={selected ? 'primary' : 'secondary'}
                onClick={() => props.onTemplate(template.id)}>
                {selected ? 'Выбрано' : 'Выбрать оформление'}
              </Button>
            </div>
          </article>;
        })}
      </div>
    </section>

    {editorOpen && <TemplateEditor baseTemplate={selectedTemplate}
      content={props.sample(selectedType.id)} docType={selectedType}
      onClose={() => setEditorOpen(false)}
      onSave={template => {
        props.onCreateTemplate(template);
        setEditorOpen(false);
      }} />}
  </div>;
}
