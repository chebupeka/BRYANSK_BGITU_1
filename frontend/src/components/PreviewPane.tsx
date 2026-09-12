import { useState } from 'react';
import PagePreview from './PagePreview';
import { Segmented } from './ui';
import { useElementWidth, usePointerTilt } from '../lib/hooks';
import { PAGE_WIDTH_MM } from '../lib/layout';
import type { DocumentContent, DocumentType, Template } from '../types';

const FULL_WIDTH_PX = PAGE_WIDTH_MM * (96 / 25.4);

interface Props {
  content: DocumentContent;
  docType: DocumentType;
  template: Template;
  /** True once the backend has prepared the content; before that the page shows the draft. */
  prepared: boolean;
  focusId?: string;
}

export default function PreviewPane({ content, docType, template, prepared, focusId }: Props) {
  const [zoom, setZoom] = useState<'fit' | 'full'>('fit');
  const [box, width] = useElementWidth<HTMLDivElement>();
  const tilt = usePointerTilt<HTMLDivElement>(3);
  const pageWidth = zoom === 'full' ? FULL_WIDTH_PX : Math.max(0, width);

  return <aside className="preview-pane" aria-label="Предпросмотр документа">
    <div className="preview-head">
      <div>
        <p className="eyebrow">Лист A4</p>
        <p className="preview-title">{docType.name}</p>
      </div>
      <Segmented label="Масштаб страницы" value={zoom} onChange={setZoom} options={[
        { value: 'fit', label: 'По ширине', title: 'Страница подгоняется под колонку' },
        { value: 'full', label: '100 %', title: 'Реальный размер листа' },
      ]} />
    </div>

    <div className={`preview-stage zoom-${zoom}`}>
      <div className="preview-viewport" ref={box}>
        <div className="page-tilt" ref={tilt.ref}
          {...(zoom === 'fit' ? tilt.handlers : {})}
          data-flat={zoom === 'full' ? 'yes' : undefined}>
          <span className="page-shadow" aria-hidden="true" />
          <PagePreview content={content} docType={docType} template={template}
            width={pageWidth} focusId={focusId} />
        </div>
      </div>
    </div>

    <p className="preview-note">
      {prepared
        ? `Подготовленное содержание · оформление «${template.name}»`
        : 'Предварительный вид: абзацы взяты прямо из черновика. Подготовка уточнит текст.'}
    </p>
  </aside>;
}
