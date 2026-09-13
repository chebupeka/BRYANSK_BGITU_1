import { Fragment, type CSSProperties } from 'react';
import { useElementHeight } from '../lib/hooks';
import {
  arrangeBlocks, COMPACT_BLOCKS, PAGE_WIDTH_MM, resolveTemplate, spaceBeforePt,
  TABLE_LABEL_WIDTH_MM, type BlockItem, type BlockKind, type PageBlock, type ResolvedTemplate,
} from '../lib/layout';
import type { DocumentContent, DocumentType, Template } from '../types';

const MM_TO_PX = 96 / 25.4;

interface Props {
  content: DocumentContent;
  docType: DocumentType;
  template: Template;
  /** Width available for the page, in CSS pixels. The sheet scales to fit it. */
  width: number;
  /** Requisite the person is editing right now: its block lights up on the page. */
  focusId?: string;
  /** In text mode the prepared body and visible requisites are edited on the sheet itself. */
  editable?: boolean;
  onBodyDraft?: (text: string) => void;
  onBodyChange?: (text: string) => void;
  onRequisiteDraft?: (id: string, value: string) => void;
  onRequisiteChange?: (id: string, value: string) => void;
  onFocusField?: (fieldId: string | undefined) => void;
}

function fontStack(font: string): string {
  const serif = /times|serif|georgia|garamond|minion/i.test(font);
  return `"${font}", ${serif ? 'Georgia, "Times New Roman", serif' : 'Arial, Helvetica, sans-serif'}`;
}

function isPlaceholder(item: BlockItem): boolean {
  return !item.value;
}

/** Text of one requisite, editable in place when the sheet is in text mode. */
function movesToDocumentAction(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest('[data-document-action]'));
}

function ItemText({ item, editable, onDraft, onChange, onFocusField }: {
  item: BlockItem;
  editable: boolean;
  onDraft?: (id: string, value: string) => void;
  onChange?: (id: string, value: string) => void;
  onFocusField?: (fieldId: string | undefined) => void;
}) {
  if (editable) return <>
    {item.field.prefix}
    <span key={item.value} className="page-editable-value" contentEditable="plaintext-only"
      suppressContentEditableWarning spellCheck role="textbox"
      aria-label={item.field.label} data-placeholder={`[Заполнить: ${item.field.label}]`}
      onFocus={() => onFocusField?.(item.field.id)}
      onInput={event => onDraft?.(
        item.field.id, (event.currentTarget.textContent ?? '').slice(0, 500),
      )}
      onBlur={event => {
        const value = (event.currentTarget.textContent ?? '').slice(0, 500);
        onDraft?.(item.field.id, value);
        if (!movesToDocumentAction(event.relatedTarget)) onChange?.(item.field.id, value);
        onFocusField?.(undefined);
      }}>{item.value}</span>
  </>;
  if (!isPlaceholder(item)) return <>{item.text}</>;
  return <>
    {item.field.prefix}
    <span className="page-placeholder">[Заполнить: {item.field.label}]</span>
  </>;
}

export default function PagePreview({
  content, docType, template, width, focusId, editable = false,
  onBodyDraft, onBodyChange, onRequisiteDraft, onRequisiteChange, onFocusField,
}: Props) {
  const [pageRef, naturalHeight] = useElementHeight<HTMLDivElement>();
  const style = resolveTemplate(template);
  const blocks = arrangeBlocks(content, docType);
  const scale = width > 0 ? width / (PAGE_WIDTH_MM * MM_TO_PX) : 1;

  const letterheadInHeader = style.header === 'organization';
  const headerItems = letterheadInHeader
    ? blocks.filter(block => block.kind === 'letterhead').flatMap(block => block.items)
    : [];
  const flow = blocks.filter(block => !(letterheadInHeader && block.kind === 'letterhead'));

  const pageStyle: CSSProperties = {
    fontFamily: fontStack(style.font),
    fontSize: `${style.fontSize}pt`,
    lineHeight: style.lineSpacing,
    paddingTop: `${style.margins.top}mm`,
    paddingRight: `${style.margins.right}mm`,
    paddingBottom: `${style.margins.bottom}mm`,
    paddingLeft: `${style.margins.left}mm`,
  };

  let previous: BlockKind | null = null;
  const rendered = flow.map((block, index) => {
    const gap = spaceBeforePt(block.kind, previous, style);
    previous = block.kind;
    return <div key={`${block.kind}-${index}`} className="page-block"
      style={{ marginTop: `${gap}pt` }} data-kind={block.kind}>
      <Block block={block} style={style} content={content} docType={docType} focusId={focusId}
        editable={editable} onBodyDraft={onBodyDraft} onBodyChange={onBodyChange}
        onRequisiteDraft={onRequisiteDraft} onRequisiteChange={onRequisiteChange}
        onFocusField={onFocusField} />
    </div>;
  });

  // The sheet is laid out at its real size and scaled into the column it lives in; the
  // wrapper takes the scaled height so the rest of the page flows around it.
  return <div className="page-scaler" style={{
    width: width > 0 ? `${width}px` : undefined,
    height: naturalHeight > 0 ? `${naturalHeight * scale}px` : undefined,
  }}>
    <div className={`page ${editable ? 'is-editing' : ''}`} ref={pageRef}
      style={{ ...pageStyle, transform: `scale(${scale})` }} lang="ru">
      {(headerItems.length > 0 || style.footer !== 'none') && <>
        {headerItems.length > 0 && <div className="page-running page-running-top" style={{
          top: `${style.margins.top / 2}mm`,
          left: `${style.margins.left}mm`,
          right: `${style.margins.right}mm`,
          fontSize: `${style.headerFooterFontSize}pt`,
          textAlign: style.letterheadAlignment,
        }}>
          {headerItems.map(item => <p key={item.field.id}><ItemText item={item}
            editable={editable} onDraft={onRequisiteDraft}
            onChange={onRequisiteChange} onFocusField={onFocusField} /></p>)}
        </div>}
        {style.footer !== 'none' && <div className="page-running page-running-bottom" style={{
          bottom: `${style.margins.bottom / 2}mm`,
          left: `${style.margins.left}mm`,
          right: `${style.margins.right}mm`,
          fontSize: `${style.headerFooterFontSize}pt`,
          textAlign: style.footer === 'page_number' ? 'center' : style.letterheadAlignment,
        }}>
          <p>{style.footer === 'page_number'
            ? '1'
            : `${docType.name}${(content.requisites.date ?? '').trim() ? ` от ${content.requisites.date.trim()}` : ''}`}</p>
        </div>}
      </>}
      {rendered}
    </div>
  </div>;
}

interface BlockProps {
  block: PageBlock;
  style: ResolvedTemplate;
  content: DocumentContent;
  docType: DocumentType;
  focusId?: string;
  editable?: boolean;
  onBodyDraft?: (text: string) => void;
  onBodyChange?: (text: string) => void;
  onRequisiteDraft?: (id: string, value: string) => void;
  onRequisiteChange?: (id: string, value: string) => void;
  onFocusField?: (fieldId: string | undefined) => void;
}

function Block({
  block, style, content, docType, focusId, editable = false,
  onBodyDraft, onBodyChange, onRequisiteDraft, onRequisiteChange, onFocusField,
}: BlockProps) {
  const compact = COMPACT_BLOCKS.has(block.kind);
  const base: CSSProperties = compact ? { lineHeight: 1 } : {};
  const innerGap = block.kind === 'addressee' ? `${style.fontSize / 2}pt` : '0pt';
  // The requisite being edited lights up on the page, so the form and the sheet stay linked.
  const mark = (item: BlockItem): CSSProperties => (item.field.id === focusId
    ? { background: 'rgba(16, 18, 20, 0.1)', boxShadow: '0 0 0 3px rgba(16, 18, 20, 0.1)', borderRadius: '2px' }
    : {});

  switch (block.kind) {
    case 'title':
      return <p className="page-title" style={{
        ...base,
        fontSize: `${style.fontSize + 2}pt`,
        textAlign: style.titleAlignment,
        marginTop: '16pt',
        marginBottom: '12pt',
      }}>{docType.title}</p>;

    case 'body':
      return <div key={content.body.join('\u0000')}
        className={`page-body-editor ${editable ? 'is-editable' : ''}`}
        contentEditable={editable ? 'plaintext-only' : undefined}
        suppressContentEditableWarning={editable || undefined}
        spellCheck={editable || undefined} role={editable ? 'textbox' : undefined}
        aria-label={editable ? 'Основной текст документа' : undefined}
        data-placeholder="Введите основной текст документа"
        onInput={editable ? event => {
          onBodyDraft?.(event.currentTarget.innerText.slice(0, 20_000));
        } : undefined}
        onBlur={editable ? event => {
          const text = event.currentTarget.innerText.slice(0, 20_000);
          if (event.currentTarget.innerText.length > 20_000) event.currentTarget.innerText = text;
          onBodyDraft?.(text);
          if (!movesToDocumentAction(event.relatedTarget)) onBodyChange?.(text);
        } : undefined}>
        {content.body.map((paragraph, index) => <p key={index} className="page-paragraph" style={{
          textAlign: style.bodyAlignment,
          textIndent: `${style.firstLineIndentMm}mm`,
          marginBottom: `${style.spaceAfterPt}pt`,
          fontWeight: style.bodyBold ? 700 : 400,
          fontStyle: style.bodyItalic ? 'italic' : 'normal',
          textDecoration: style.bodyUnderline ? 'underline' : 'none',
        }}>{paragraph}</p>)}
      </div>;

    case 'letterhead':
      return <>{block.items.map(item => <p key={item.field.id} data-requisite={item.field.id}
        style={{ ...base, ...mark(item), textAlign: style.letterheadAlignment }}>
        <ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
          onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;

    case 'addressee':
      if (style.recipientLayout === 'table') {
        return <table className="page-table" style={base}>
          <tbody>
            {block.items.map(item => <tr key={item.field.id} data-requisite={item.field.id}
              style={mark(item)}>
              <th scope="row" style={{ width: `${TABLE_LABEL_WIDTH_MM}mm` }}>{item.field.label}</th>
              <td><ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
                onChange={onRequisiteChange}
                onFocusField={onFocusField} /></td>
            </tr>)}
          </tbody>
        </table>;
      }
      return <>{block.items.map((item, index) => <p key={item.field.id} data-requisite={item.field.id}
        style={{
          ...base, ...mark(item),
          // The corner block starts in the right part of the page and wraps inside it.
          marginLeft: style.recipientAlignment === 'right'
            ? `${style.textWidthMm - style.addresseeWidthMm}mm` : undefined,
          textAlign: style.recipientAlignment === 'right' ? 'left' : style.recipientAlignment,
          marginBottom: index < block.items.length - 1 ? innerGap : undefined,
        }}>
        <ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
          onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;

    case 'registration':
      return <p style={base} data-requisite={block.items[0]?.field.id}>
        {block.items.map((item, index) => <Fragment key={item.field.id}>
          {index > 0 && ' '}
          <span style={mark(item)}><ItemText item={item} editable={editable}
            onDraft={onRequisiteDraft} onChange={onRequisiteChange}
            onFocusField={onFocusField} /></span>
        </Fragment>)}
      </p>;

    case 'headline':
      return <p style={{
        ...base, textAlign: style.headlineAlignment, fontWeight: style.headlineBold ? 700 : 400,
      }} data-requisite={block.items[0]?.field.id}>
        {block.items.map((item, index) => <Fragment key={item.field.id}>
          {index > 0 && ' '}
          <span style={mark(item)}><ItemText item={item} editable={editable}
            onDraft={onRequisiteDraft} onChange={onRequisiteChange}
            onFocusField={onFocusField} /></span>
        </Fragment>)}
      </p>;

    case 'salutation':
      return <>{block.items.map(item => <p key={item.field.id} data-requisite={item.field.id}
        style={{ ...base, ...mark(item), textAlign: style.titleAlignment }}>
        <ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
          onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;

    case 'signature': {
      if (style.signatureAlignment === 'left' && block.items.length > 1) {
        const left = block.items.slice(0, -1);
        const last = block.items[block.items.length - 1];
        // Position on the left, name at the right margin: «Заведующий   И. И. Иванов».
        return <p className="page-signature" style={base}>
          <span>{left.map((item, index) => <Fragment key={item.field.id}>
            {index > 0 && ' '}
            <span data-requisite={item.field.id} style={mark(item)}><ItemText item={item}
              editable={editable} onDraft={onRequisiteDraft}
              onChange={onRequisiteChange} onFocusField={onFocusField} /></span>
          </Fragment>)}</span>
          <span data-requisite={last.field.id} style={mark(last)}><ItemText item={last}
            editable={editable} onDraft={onRequisiteDraft}
            onChange={onRequisiteChange} onFocusField={onFocusField} /></span>
        </p>;
      }
      return <>{block.items.map(item => <p key={item.field.id} data-requisite={item.field.id}
        style={{ ...base, ...mark(item), textAlign: style.signatureAlignment }}>
        <ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
          onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;
    }

    case 'executor':
      return <>{block.items.map(item => <p key={item.field.id} data-requisite={item.field.id}
        style={{ ...base, ...mark(item), fontSize: `${style.smallFontSize}pt` }}>
        <ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
          onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;

    case 'paragraph':
      return <>{block.items.map(item => <p key={item.field.id} data-requisite={item.field.id}
        style={{ ...base, ...mark(item) }}>
        <ItemText item={item} editable={editable} onDraft={onRequisiteDraft}
          onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;

    default:
      // «Подпись поля: значение» — requisites without a standard position on the page.
      return <>{block.items.map(item => <p key={item.field.id} data-requisite={item.field.id}
        style={{
          ...base, ...mark(item),
          textAlign: item.field.id === 'recipient' || item.field.id === 'sender'
            ? style.recipientAlignment : undefined,
        }}>
        <strong>{item.field.label}: </strong><ItemText item={item} editable={editable}
          onDraft={onRequisiteDraft} onChange={onRequisiteChange}
          onFocusField={onFocusField} />
      </p>)}</>;
  }
}
