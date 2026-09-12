import { Button } from '../components/ui';
import { ArrowRight, Download, Document, Layers } from '../components/icons';
import { useReveal } from '../lib/hooks';

interface Props {
  hasDraft: boolean;
  onStart: () => void;
  onCatalog: () => void;
  onSample: () => void;
}

const STORY = [
  { icon: <Document size={22} />, title: '1. Добавьте текст', text: 'Напишите своими словами или вставьте готовый черновик.' },
  { icon: <Layers size={22} />, title: '2. Укажите детали', text: 'Выберите тип документа, заполните реквизиты и настройте оформление.' },
  { icon: <Download size={22} />, title: '3. Скачайте документ', text: 'Проверьте результат и сохраните файл Word — его можно редактировать.' },
];

export default function HomePage(props: Props) {
  const reveal = useReveal<HTMLElement>();

  return <div className="view view-home">
    <section className="hero">
      <div className="hero-inner">
        <h1 className="hero-title">
          Деловой документ
          <span> из вашего черновика.</span>
        </h1>
        <p className="hero-lead">Подготовьте письмо, записку или справку: от простого текста до оформленного файла Word за три шага.</p>

        <div className="hero-actions">
          <Button variant="primary" size="xl" onClick={props.onStart}
            iconRight={<ArrowRight size={20} />}>
            {props.hasDraft ? 'Продолжить документ' : 'Создать документ'}
          </Button>
        </div>

        <div className="hero-links">
          <button type="button" onClick={props.onCatalog}>Типы документов</button>
          <button type="button" onClick={props.onSample}>Попробовать на примере</button>
        </div>
      </div>
    </section>

    <section className="story reveal" ref={reveal}>
      {STORY.map(item => <article key={item.title} className="story-card">
        <span className="story-icon" aria-hidden="true">{item.icon}</span>
        <h2>{item.title}</h2>
        <p>{item.text}</p>
      </article>)}
    </section>

  </div>;
}
