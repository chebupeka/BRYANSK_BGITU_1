import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { createPortal } from 'react-dom';
import PagePreview from './PagePreview';
import { Button, Field, Segmented } from './ui';
import { Check, Close, Refresh } from './icons';
import type { Alignment, DocumentContent, DocumentType, Template } from '../types';

interface Props {
  docTypes: DocumentType[];
  initialDocTypeId: string;
  sample: (docTypeId: string) => DocumentContent;
  onClose: () => void;
  onSave: (template: Template) => void;
}

type MarginSide = 'top' | 'right' | 'bottom' | 'left';

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

/** A neutral starting point owned by the editor, never copied from a catalog template. */
function initialTemplate(): Template {
  return {
    id: 'custom_preview',
    name: 'Новое оформление',
    description: 'Собственное оформление документа',
    font: 'Times New Roman',
    font_size: 14,
    margins_mm: { top: 20, right: 15, bottom: 20, left: 30 },
    line_spacing: 1.5,
    paragraph_space_after_pt: 0,
    first_line_indent_mm: 12.5,
    title_alignment: 'center',
    recipient_alignment: 'right',
    body_alignment: 'justify',
    signature_alignment: 'left',
    recipient_layout: 'block',
    header: 'none',
    footer: 'none',
    header_footer_font_size: 10,
    letterhead_alignment: 'center',
    headline_alignment: 'left',
    headline_bold: false,
    body_bold: false,
    body_italic: false,
    body_underline: false,
    addressee_width_mm: 80,
    small_font_size: 10,
  };
}

function numberFrom(event: ChangeEvent<HTMLInputElement>, fallback: number): number {
  const value = Number(event.target.value);
  return Number.isFinite(value) ? value : fallback;
}

export default function TemplateEditor({
  docTypes, initialDocTypeId, sample, onClose, onSave,
}: Props) {
  const [template, setTemplate] = useState(initialTemplate);
  const [previewTypeId, setPreviewTypeId] = useState(initialDocTypeId);
  const nameRef = useRef<HTMLInputElement>(null);
  const previewType = docTypes.find(item => item.id === previewTypeId) ?? docTypes[0];
  const activePlacements = new Set(previewType.fields
    .filter(field => previewType.blocks.includes(field.id))
    .map(field => field.placement ?? 'labeled'));
  const hasTitle = previewType.show_title !== false && previewType.blocks.includes('title');
  const hasSalutation = activePlacements.has('salutation');
  const hasHeadline = activePlacements.has('headline');
  const hasAddressee = activePlacements.has('addressee');
  const hasSignature = activePlacements.has('signature');
  const hasLetterhead = activePlacements.has('letterhead');
  const hasExecutor = activePlacements.has('executor');
  const hasRunningContent = (hasLetterhead && template.header === 'organization')
    || template.footer !== 'none';
  const hasLetterheadAlignment = hasLetterhead || template.footer === 'title_and_date';

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

  function margin(side: MarginSide, value: number) {
    setTemplate(current => ({
      ...current,
      margins_mm: { ...current.margins_mm, [side]: value },
    }));
  }

  function resetSettings() {
    setTemplate(current => ({
      ...initialTemplate(),
      name: current.name,
      description: current.description,
    }));
  }

  const validName = template.name.trim();

  return createPortal(<div className="template-editor-backdrop" role="presentation"
    onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="template-editor" role="dialog" aria-modal="true"
      aria-labelledby="template-editor-title">
      <header className="template-editor-head">
        <div>
          <p className="eyebrow">Чистый шаблон</p>
          <h2 id="template-editor-title">Подробный редактор оформления</h2>
          <p>Настройки начинаются с нейтральных значений и не копируют готовое оформление.</p>
        </div>
        <Button variant="quiet" icon={<Close size={18} />} onClick={onClose}
          aria-label="Закрыть редактор">Закрыть</Button>
      </header>

      <div className="template-editor-body">
        <aside className="template-editor-preview">
          <div className="editor-preview-head">
            <p className="group-title">Предпросмотр</p>
            <label className="preview-type-label" htmlFor="preview-document-type">Тип документа</label>
            <select id="preview-document-type" className="input" value={previewType.id}
              onChange={event => setPreviewTypeId(event.target.value)}>
              {docTypes.map(type => <option key={type.id} value={type.id}>{type.name}</option>)}
            </select>
          </div>
          <div className="template-editor-sheet" aria-live="polite">
            <PagePreview content={sample(previewType.id)} docType={previewType}
              template={template} width={334} />
          </div>
          <div className="editor-preview-facts" aria-label="Текущие параметры">
            <span>{template.font} · {template.font_size} пт</span>
            <span>Интервал {template.line_spacing.toString().replace('.', ',')}</span>
            <span>Поля {template.margins_mm.top}/{template.margins_mm.right}/
              {template.margins_mm.bottom}/{template.margins_mm.left} мм</span>
          </div>
        </aside>

        <form className="template-editor-form" onSubmit={event => {
          event.preventDefault();
          if (!validName) return;
          onSave({ ...template, id: customId(), name: validName });
        }}>
          <div className="editor-form-heading">
            <div>
              <h3>Параметры документа</h3>
              <p>Все параметры сохраняются в новом оформлении.</p>
            </div>
            <Button variant="quiet" icon={<Refresh size={16} />} onClick={resetSettings}>
              Сбросить настройки
            </Button>
          </div>

          <fieldset className="editor-group">
            <legend>Название</legend>
            <div className="editor-fields editor-fields-wide">
              <Field id="template-name" label="Название оформления" required>
                <input ref={nameRef} id="template-name" className="input" maxLength={80}
                  value={template.name} onChange={event => patch({ name: event.target.value })} />
              </Field>
              <Field id="template-description" label="Краткое описание">
                <input id="template-description" className="input" maxLength={240}
                  value={template.description}
                  onChange={event => patch({ description: event.target.value })} />
              </Field>
            </div>
          </fieldset>

          <fieldset className="editor-group">
            <legend>Основной текст</legend>
            <div className="editor-fields editor-fields-three">
              <Field id="template-font" label="Шрифт">
                <input id="template-font" className="input" list="template-font-options" maxLength={80}
                  value={template.font} onChange={event => patch({ font: event.target.value })} />
                <datalist id="template-font-options">
                  {FONTS.map(font => <option key={font} value={font} />)}
                </datalist>
              </Field>
              <Field id="template-font-size" label="Размер, пт">
                <input id="template-font-size" className="input" type="number" min="10" max="16" step="0.5"
                  value={template.font_size}
                  onChange={event => patch({ font_size: numberFrom(event, template.font_size) })} />
              </Field>
              <Field id="template-line-spacing" label="Межстрочный интервал">
                <input id="template-line-spacing" className="input" type="number" min="1" max="2" step="0.05"
                  value={template.line_spacing}
                  onChange={event => patch({ line_spacing: numberFrom(event, template.line_spacing) })} />
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
              {hasExecutor && <Field id="template-small-size" label="Мелкий текст, пт"
                hint="Исполнитель и служебные строки">
                <input id="template-small-size" className="input" type="number" min="8" max="14" step="0.5"
                  value={template.small_font_size}
                  onChange={event => patch({ small_font_size: numberFrom(event, template.small_font_size) })} />
              </Field>}
            </div>
            <div className="editor-alignment">
              <span className="field-label">Выравнивание основного текста</span>
              <Segmented label="Выравнивание основного текста" value={template.body_alignment}
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

          {(hasTitle || hasSalutation || hasHeadline) && <fieldset className="editor-group">
            <legend>Заголовки</legend>
            <div className="editor-alignment-grid">
              {(hasTitle || hasSalutation) && <div className="editor-alignment">
                <span className="field-label">Название документа</span>
                <Segmented label="Выравнивание названия документа" value={template.title_alignment}
                  options={ALIGNMENTS} onChange={value => patch({ title_alignment: value })} />
              </div>}
              {hasHeadline && <div className="editor-alignment">
                <span className="field-label">Тема документа</span>
                <Segmented label="Выравнивание темы документа" value={template.headline_alignment}
                  options={ALIGNMENTS} onChange={value => patch({ headline_alignment: value })} />
              </div>}
            </div>
            {hasHeadline && <label className="editor-check">
              <input type="checkbox" checked={template.headline_bold}
                onChange={event => patch({ headline_bold: event.target.checked })} />
              <span><strong>Выделять тему полужирным</strong><small>Применяется к теме перед основным текстом.</small></span>
            </label>}
          </fieldset>}

          {(hasAddressee || hasSignature) && <fieldset className="editor-group">
            <legend>Адресат и подпись</legend>
            {hasAddressee && <div className="editor-fields">
              <Field id="template-recipient-layout" label="Вид адресата">
                <select id="template-recipient-layout" className="input" value={template.recipient_layout}
                  onChange={event => patch({ recipient_layout: event.target.value as Template['recipient_layout'] })}>
                  <option value="block">Текстовый блок</option>
                  <option value="table">Таблица</option>
                </select>
              </Field>
              {template.recipient_layout === 'block' && <Field id="template-addressee-width" label="Ширина адресата, мм"
                hint="Для правого текстового блока">
                <input id="template-addressee-width" className="input" type="number" min="50" max="120" step="1"
                  value={template.addressee_width_mm}
                  onChange={event => patch({ addressee_width_mm: numberFrom(event, template.addressee_width_mm) })} />
              </Field>}
            </div>}
            <div className="editor-alignment-grid">
              {hasAddressee && template.recipient_layout === 'block' && <div className="editor-alignment">
                <span className="field-label">Выравнивание адресата</span>
                <Segmented label="Выравнивание адресата" value={template.recipient_alignment}
                  options={ALIGNMENTS} onChange={value => patch({ recipient_alignment: value })} />
              </div>}
              {hasSignature && <div className="editor-alignment">
                <span className="field-label">Выравнивание подписи</span>
                <Segmented label="Выравнивание подписи" value={template.signature_alignment}
                  options={ALIGNMENTS} onChange={value => patch({ signature_alignment: value })} />
              </div>}
            </div>
          </fieldset>}

          <fieldset className="editor-group">
            <legend>Колонтитулы и организация</legend>
            <div className="editor-fields editor-fields-three">
              {hasLetterhead && <Field id="template-header" label="Организация">
                <select id="template-header" className="input" value={template.header}
                  onChange={event => patch({ header: event.target.value as Template['header'] })}>
                  <option value="none">В тексте страницы</option>
                  <option value="organization">В верхнем колонтитуле</option>
                </select>
              </Field>}
              <Field id="template-footer" label="Нижний колонтитул">
                <select id="template-footer" className="input" value={template.footer}
                  onChange={event => patch({ footer: event.target.value as Template['footer'] })}>
                  <option value="none">Без колонтитула</option>
                  <option value="page_number">Номер страницы</option>
                  <option value="title_and_date">Тип документа и дата</option>
                </select>
              </Field>
              {hasRunningContent && <Field id="template-running-size" label="Размер колонтитула, пт">
                <input id="template-running-size" className="input" type="number" min="8" max="14" step="0.5"
                  value={template.header_footer_font_size}
                  onChange={event => patch({ header_footer_font_size: numberFrom(event, template.header_footer_font_size) })} />
              </Field>}
            </div>
            {hasLetterheadAlignment && <div className="editor-alignment">
              <span className="field-label">{template.footer === 'title_and_date'
                ? 'Выравнивание организации и нижнего колонтитула'
                : 'Выравнивание организации'}</span>
              <Segmented label="Выравнивание организации и нижнего колонтитула"
                value={template.letterhead_alignment} options={ALIGNMENTS}
                onChange={value => patch({ letterhead_alignment: value })} />
            </div>}
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
