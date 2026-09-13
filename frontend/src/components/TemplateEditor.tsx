import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { createPortal } from 'react-dom';
import PagePreview from './PagePreview';
import { Button, Field, Segmented } from './ui';
import { Check, Close } from './icons';
import type { Alignment, DocumentContent, DocumentType, Template } from '../types';

interface Props {
  baseTemplate: Template;
  content: DocumentContent;
  docType: DocumentType;
  onClose: () => void;
  onSave: (template: Template) => void;
}

const ALIGNMENTS: { value: Alignment; label: string }[] = [
  { value: 'left', label: 'Слева' },
  { value: 'center', label: 'По центру' },
  { value: 'right', label: 'Справа' },
  { value: 'justify', label: 'По ширине' },
];

const FONTS = ['Times New Roman', 'Arial', 'Calibri', 'Georgia', 'PT Serif'];

function customId(): string {
  const random = Math.random().toString(36).slice(2, 7);
  return `custom_${Date.now().toString(36)}_${random}`;
}

function initialTemplate(base: Template): Template {
  return {
    ...base,
    id: 'custom_preview',
    name: 'Моё оформление',
    description: 'Пользовательское оформление',
    margins_mm: { ...base.margins_mm },
  };
}

function numberFrom(event: ChangeEvent<HTMLInputElement>, fallback: number): number {
  const value = Number(event.target.value);
  return Number.isFinite(value) ? value : fallback;
}

export default function TemplateEditor({ baseTemplate, content, docType, onClose, onSave }: Props) {
  const [template, setTemplate] = useState(() => initialTemplate(baseTemplate));
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    nameRef.current?.focus({ preventScroll: true });
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose]);

  function patch(next: Partial<Template>) {
    setTemplate(current => ({ ...current, ...next }));
  }

  function margin(side: 'top' | 'right' | 'bottom' | 'left', value: number) {
    setTemplate(current => ({
      ...current,
      margins_mm: { ...current.margins_mm, [side]: value },
    }));
  }

  const validName = template.name.trim();

  return createPortal(<div className="template-editor-backdrop" role="presentation"
    onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="template-editor" role="dialog" aria-modal="true"
      aria-labelledby="template-editor-title">
      <header className="template-editor-head">
        <div>
          <p className="eyebrow">Новое оформление</p>
          <h2 id="template-editor-title">Редактор оформления</h2>
          <p>Настройте страницу и сразу оцените результат в предпросмотре.</p>
        </div>
        <Button variant="quiet" icon={<Close size={18} />} onClick={onClose}
          aria-label="Закрыть редактор">Закрыть</Button>
      </header>

      <div className="template-editor-body">
        <div className="template-editor-preview">
          <p className="group-title">Предпросмотр</p>
          <div className="template-editor-sheet" aria-live="polite">
            <PagePreview content={content} docType={docType} template={template} width={334} />
          </div>
          <p className="template-editor-note">Предпросмотр показывает выбранный тип документа.</p>
        </div>

        <form className="template-editor-form" onSubmit={event => {
          event.preventDefault();
          if (!validName) return;
          onSave({ ...template, id: customId(), name: validName });
        }}>
          <div className="editor-fields editor-fields-wide">
            <Field id="template-name" label="Название" required>
              <input ref={nameRef} id="template-name" className="input" maxLength={80}
                value={template.name} onChange={event => patch({ name: event.target.value })} />
            </Field>
            <Field id="template-font" label="Шрифт">
              <select id="template-font" className="input" value={template.font}
                onChange={event => patch({ font: event.target.value })}>
                {[...new Set([template.font, ...FONTS])].map(font => <option key={font}>{font}</option>)}
              </select>
            </Field>
          </div>

          <fieldset className="editor-group">
            <legend>Текст</legend>
            <div className="editor-fields">
              <Field id="template-font-size" label="Размер, пт">
                <input id="template-font-size" className="input" type="number" min="10" max="16" step="0.5"
                  value={template.font_size}
                  onChange={event => patch({ font_size: numberFrom(event, template.font_size) })} />
              </Field>
              <Field id="template-line-spacing" label="Межстрочный интервал">
                <select id="template-line-spacing" className="input" value={template.line_spacing}
                  onChange={event => patch({ line_spacing: Number(event.target.value) })}>
                  {[1, 1.15, 1.5, 2].map(value => <option key={value} value={value}>{value}</option>)}
                </select>
              </Field>
              <Field id="template-indent" label="Красная строка, мм">
                <input id="template-indent" className="input" type="number" min="0" max="20" step="0.5"
                  value={template.first_line_indent_mm}
                  onChange={event => patch({ first_line_indent_mm: numberFrom(event, template.first_line_indent_mm) })} />
              </Field>
              <Field id="template-space" label="После абзаца, пт">
                <input id="template-space" className="input" type="number" min="0" max="24" step="1"
                  value={template.paragraph_space_after_pt}
                  onChange={event => patch({ paragraph_space_after_pt: numberFrom(event, template.paragraph_space_after_pt) })} />
              </Field>
            </div>
            <div className="editor-alignment">
              <span className="field-label">Выравнивание текста</span>
              <Segmented label="Выравнивание текста" value={template.body_alignment}
                options={ALIGNMENTS} onChange={value => patch({ body_alignment: value })} />
            </div>
          </fieldset>

          <fieldset className="editor-group">
            <legend>Поля страницы, мм</legend>
            <div className="editor-fields editor-margins">
              {([
                ['top', 'Сверху'], ['right', 'Справа'], ['bottom', 'Снизу'], ['left', 'Слева'],
              ] as const).map(([side, label]) => <Field key={side} id={`margin-${side}`} label={label}>
                <input id={`margin-${side}`} className="input" type="number" min="5" max="50" step="1"
                  value={template.margins_mm[side]}
                  onChange={event => margin(side, numberFrom(event, template.margins_mm[side]))} />
              </Field>)}
            </div>
          </fieldset>

          <fieldset className="editor-group">
            <legend>Структура</legend>
            <div className="editor-fields editor-fields-wide">
              <Field id="template-recipient" label="Блок адресата">
                <select id="template-recipient" className="input" value={template.recipient_layout}
                  onChange={event => patch({ recipient_layout: event.target.value as Template['recipient_layout'] })}>
                  <option value="block">Текстовый блок</option>
                  <option value="table">Таблица</option>
                </select>
              </Field>
              <Field id="template-footer" label="Нижний колонтитул">
                <select id="template-footer" className="input" value={template.footer}
                  onChange={event => patch({ footer: event.target.value as Template['footer'] })}>
                  <option value="none">Без колонтитула</option>
                  <option value="page_number">Номер страницы</option>
                  <option value="title_and_date">Тип документа и дата</option>
                </select>
              </Field>
            </div>
            <label className="editor-check">
              <input type="checkbox" checked={template.headline_bold}
                onChange={event => patch({ headline_bold: event.target.checked })} />
              <span><strong>Выделять тему полужирным</strong><small>Применяется к заголовку перед основным текстом.</small></span>
            </label>
          </fieldset>

          <footer className="template-editor-actions">
            <Button variant="quiet" onClick={onClose}>Отменить</Button>
            <Button variant="primary" icon={<Check size={17} />} type="submit" disabled={!validName}>
              Сохранить оформление
            </Button>
          </footer>
        </form>
      </div>
    </section>
  </div>, document.body);
}
