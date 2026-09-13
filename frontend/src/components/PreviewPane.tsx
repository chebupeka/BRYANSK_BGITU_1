import { useEffect, useState } from 'react';
import PagePreview from './PagePreview';
import { Segmented } from './ui';
import { AlignCenter, AlignJustify, AlignLeft, AlignRight } from './icons';
import { useElementWidth, usePointerTilt } from '../lib/hooks';
import { EDITOR_FONTS, PAGE_WIDTH_MM, resolveTemplate, splitParagraphs } from '../lib/layout';
import type { Alignment, DocumentContent, DocumentFormatting, DocumentType, Template } from '../types';

const FULL_WIDTH_PX = PAGE_WIDTH_MM * (96 / 25.4);

interface Props {
  content: DocumentContent;
  docType: DocumentType;
  template: Template;
  /** True once the backend has prepared the content; before that the page shows the draft. */
  prepared: boolean;
  focusId?: string;
  templates?: Template[];
  formatting: DocumentFormatting;
  formattingCustomized?: boolean;
  disabled?: boolean;
  onContentDraftChange?: (content: DocumentContent) => void;
  onContentChange?: (content: DocumentContent) => void;
  onTemplate?: (templateId: string) => void;
  onFormattingChange?: (formatting: DocumentFormatting | null) => void;
  onFocusField?: (fieldId: string | undefined) => void;
}

type EditorMode = 'preview' | 'text' | 'style';

export default function PreviewPane({
  content, docType, template, prepared, focusId, templates = [], disabled = false,
  formatting, formattingCustomized = false,
  onContentDraftChange, onContentChange, onTemplate, onFormattingChange, onFocusField,
}: Props) {
  const [zoom, setZoom] = useState<'fit' | 'full'>('fit');
  const [mode, setMode] = useState<EditorMode>('preview');
  const [box, width] = useElementWidth<HTMLDivElement>();
  const tilt = usePointerTilt<HTMLDivElement>(3);
  const pageWidth = zoom === 'full' ? FULL_WIDTH_PX : Math.max(0, width);
  const editable = prepared && Boolean(onContentChange);

  useEffect(() => {
    if (!editable) setMode('preview');
  }, [editable]);

  function changeBody(value: string) {
    const body = splitParagraphs(value);
    onContentChange?.({ ...content, body });
  }

  function draftBody(value: string) {
    onContentDraftChange?.({ ...content, body: splitParagraphs(value) });
  }

  function changeRequisite(id: string, value: string) {
    onContentChange?.({
      ...content,
      requisites: { ...content.requisites, [id]: value },
    });
  }

  function draftRequisite(id: string, value: string) {
    onContentDraftChange?.({
      ...content,
      requisites: { ...content.requisites, [id]: value },
    });
  }

  function changeFormatting(patch: Partial<DocumentFormatting>) {
    onFormattingChange?.({ ...formatting, ...patch });
  }

  return <aside className="preview-pane" aria-label="Предпросмотр документа">
    <div className="preview-head">
      <div>
        <p className="eyebrow">Лист A4</p>
        <p className="preview-title">{docType.name}</p>
      </div>
      <div className="preview-controls">
        {editable && <Segmented label="Режим документа" value={mode} onChange={setMode} options={[
          { value: 'preview', label: 'Лист', title: 'Предпросмотр документа' },
          { value: 'text', label: 'Текст', title: 'Редактировать текст перед скачиванием' },
          { value: 'style', label: 'Оформление', title: 'Выбрать оформление документа' },
        ]} />}
        <Segmented label="Масштаб страницы" value={zoom} onChange={setZoom} options={[
          { value: 'fit', label: 'По ширине', title: 'Страница подгоняется под колонку' },
          { value: 'full', label: '100 %', title: 'Реальный размер листа' },
        ]} />
      </div>
    </div>

    {editable && mode === 'text' && <section className="inline-editor-bar"
      aria-labelledby="text-editor-title">
      <div className="inline-editor-head">
        <p id="text-editor-title"><strong>Редактирование на листе</strong> · нажмите на текст или реквизит</p>
        <span className="editor-counter">
          {content.body.join('\n').length.toLocaleString('ru-RU')} / 20 000
        </span>
      </div>
      <div className="editor-toolbar" role="toolbar" aria-label="Форматирование основного текста">
        <div className="toolbar-group toolbar-font">
          <label className="toolbar-select-wrap">
            <span className="sr-only">Шрифт</span>
            <select className="toolbar-select" aria-label="Шрифт" value={formatting.font}
              disabled={disabled}
              onChange={event => changeFormatting({
                font: event.target.value as DocumentFormatting['font'],
              })}>
              {EDITOR_FONTS.map(font => <option key={font} value={font}>{font}</option>)}
            </select>
          </label>
          <label className="toolbar-select-wrap toolbar-size">
            <span className="sr-only">Размер шрифта</span>
            <select className="toolbar-select" aria-label="Размер шрифта"
              value={formatting.font_size} disabled={disabled}
              onChange={event => changeFormatting({ font_size: Number(event.target.value) })}>
              {[10, 11, 12, 14, 16, 18, 20].map(size => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        </div>

        <div className="toolbar-group" aria-label="Начертание">
          <button type="button" className={`format-button ${formatting.body_bold ? 'is-active' : ''}`}
            aria-label="Полужирный" aria-pressed={formatting.body_bold} title="Полужирный"
            disabled={disabled} onClick={() => changeFormatting({ body_bold: !formatting.body_bold })}>
            <strong>Ж</strong>
          </button>
          <button type="button" className={`format-button ${formatting.body_italic ? 'is-active' : ''}`}
            aria-label="Курсив" aria-pressed={formatting.body_italic} title="Курсив"
            disabled={disabled} onClick={() => changeFormatting({ body_italic: !formatting.body_italic })}>
            <em>К</em>
          </button>
          <button type="button" className={`format-button ${formatting.body_underline ? 'is-active' : ''}`}
            aria-label="Подчёркнутый" aria-pressed={formatting.body_underline} title="Подчёркнутый"
            disabled={disabled} onClick={() => changeFormatting({ body_underline: !formatting.body_underline })}>
            <u>Ч</u>
          </button>
        </div>

        <div className="toolbar-group" aria-label="Выравнивание текста">
          {([
            { value: 'left' as Alignment, label: 'По левому краю', icon: <AlignLeft size={16} /> },
            { value: 'center' as Alignment, label: 'По центру', icon: <AlignCenter size={16} /> },
            { value: 'right' as Alignment, label: 'По правому краю', icon: <AlignRight size={16} /> },
            { value: 'justify' as Alignment, label: 'По ширине', icon: <AlignJustify size={16} /> },
          ]).map(item => <button key={item.value} type="button"
            className={`format-button ${formatting.body_alignment === item.value ? 'is-active' : ''}`}
            aria-label={item.label} aria-pressed={formatting.body_alignment === item.value}
            title={item.label} disabled={disabled}
            onClick={() => changeFormatting({ body_alignment: item.value })}>{item.icon}</button>)}
        </div>

        <div className="toolbar-group toolbar-paragraph">
          <label className="toolbar-setting">
            <span>Интервал</span>
            <select className="toolbar-select" aria-label="Межстрочный интервал"
              value={formatting.line_spacing} disabled={disabled}
              onChange={event => changeFormatting({ line_spacing: Number(event.target.value) })}>
              {[1, 1.15, 1.5, 2].map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="toolbar-setting">
            <span>После</span>
            <select className="toolbar-select" aria-label="Интервал после абзаца"
              value={formatting.paragraph_space_after_pt} disabled={disabled}
              onChange={event => changeFormatting({ paragraph_space_after_pt: Number(event.target.value) })}>
              {[0, 6, 8, 12, 18, 24].map(value => <option key={value} value={value}>{value} пт</option>)}
            </select>
          </label>
          <label className="toolbar-setting">
            <span>Отступ</span>
            <select className="toolbar-select" aria-label="Отступ первой строки"
              value={formatting.first_line_indent_mm} disabled={disabled}
              onChange={event => changeFormatting({ first_line_indent_mm: Number(event.target.value) })}>
              {[0, 5, 10, 12.5, 15, 20].map(value => <option key={value} value={value}>{value} мм</option>)}
            </select>
          </label>
        </div>

        <button type="button" className="toolbar-reset" disabled={disabled || !formattingCustomized}
          onClick={() => onFormattingChange?.(null)} title="Вернуть оформление выбранного шаблона">
          Сбросить
        </button>
      </div>
    </section>}

    {editable && mode === 'style' && <section className="preview-editor" aria-labelledby="style-editor-title">
      <div className="preview-editor-head">
        <div>
          <h3 id="style-editor-title">Оформление</h3>
          <p>Содержание не изменится, повторная обработка не нужна.</p>
        </div>
      </div>
      <div className="editor-templates" role="radiogroup" aria-label="Оформление документа">
        {templates.map(item => {
          const style = resolveTemplate(item);
          const selected = item.id === template.id;
          return <button key={item.id} type="button" role="radio" aria-checked={selected}
            disabled={disabled} className={`editor-template ${selected ? 'is-selected' : ''}`}
            onClick={() => onTemplate?.(item.id)}>
            <span className="editor-template-check" aria-hidden="true">{selected ? '✓' : ''}</span>
            <span>
              <strong>{item.name}</strong>
              <small>{style.font} · {style.fontSize} пт · интервал {style.lineSpacing}</small>
            </span>
          </button>;
        })}
      </div>
    </section>}

    <div className={`preview-stage zoom-${zoom}`}>
      <div className="preview-viewport" ref={box}>
        <div className="page-tilt" ref={tilt.ref}
          {...(zoom === 'fit' && mode !== 'text' ? tilt.handlers : {})}
          data-flat={zoom === 'full' || mode === 'text' ? 'yes' : undefined}>
          <span className="page-shadow" aria-hidden="true" />
          <PagePreview content={content} docType={docType} template={template}
            width={pageWidth} focusId={focusId} editable={editable && mode === 'text' && !disabled}
            onBodyDraft={draftBody} onBodyChange={changeBody}
            onRequisiteDraft={draftRequisite} onRequisiteChange={changeRequisite}
            onFocusField={onFocusField} />
        </div>
      </div>
    </div>

    <p className="preview-note">
      {prepared
        ? `${formattingCustomized ? 'Индивидуальное оформление' : 'Можно отредактировать перед скачиванием'} · шаблон «${template.name}»`
        : 'Предварительный вид: абзацы взяты прямо из черновика. Подготовка уточнит текст.'}
    </p>
  </aside>;
}
