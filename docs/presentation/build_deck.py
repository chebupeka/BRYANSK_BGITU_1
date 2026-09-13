"""Презентация «Документ за 3 шага» в визуальном языке самого сервиса.

Графит и пепел, почти монохромно; белый лист бумаги — единственный яркий объект.
Токены взяты из frontend/src/styles/tokens.css. Сцена 1920×1080, картинки встроены.
"""
import base64
import os
import pathlib

# По умолчанию: картинки в assets/ рядом со скриптом, результат — в ту же папку.
HERE = pathlib.Path(__file__).resolve().parent
SHOTS = pathlib.Path(os.environ.get("DECK_SHOTS", HERE / "assets"))
OUT = pathlib.Path(os.environ.get("DECK_OUT", HERE))
URL = "doc3.codeboom.pro"
TESTS = "319"
BUNDLE = "321 КБ"


def img(name):
    return "data:image/jpeg;base64," + base64.b64encode((SHOTS / f"{name}.jpg").read_bytes()).decode()


def qr():
    return "data:image/svg+xml;base64," + base64.b64encode((SHOTS / "qr.svg").read_bytes()).decode()


# Иконки в духе интерфейса: тонкий контур, без заливки.
ICON_PATHS = {
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "shield": '<path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "alert": '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17v.5"/>',
    "plug": '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "rocket": '<path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2M9 13l2 2M14 4c3-1 6-1 6-1s0 3-1 6l-7 7-5-5z"/><circle cx="15" cy="9" r="1.5"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L11.5 7M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7L12.5 17"/>',
    "building": '<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2M10 21v-3h4v3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h2.4A4.6 4.6 0 0 0 21 9.8C21 6 17 3 12 3z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="15" cy="7.5" r="1"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    "brain": '<path d="M9 4a3 3 0 0 0-3 3v.5A3 3 0 0 0 4 10.3 3 3 0 0 0 5 16a3 3 0 0 0 4 3.8V4zM15 4a3 3 0 0 1 3 3v.5a3 3 0 0 1 2 2.8 3 3 0 0 1-1 5.7 3 3 0 0 1-4 3.8V4z"/>',
    "doc_mark": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
}


def icon(name, size=30):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</svg>')


SECTIONS = ["Задача", "Решение", "Устройство", "Готовность"]
SLIDES = []

# Листы бумаги по краям сцены: как на главной сервиса, но тихо и не под текстом.
# Листы стоят только за полями сцены (x < 95 и x > 1825) и не заходят на шапку и подвал,
# иначе в печати они просвечивают сквозь карточки и ложатся на подписи.
SHEETS_SIDE = [(-70, 420, 130, -16, .14), (1840, 300, 110, 14, .13), (-50, 760, 110, 20, .11),
               (1850, 700, 120, -10, .12)]
SHEETS_HERO = [(40, 190, 200, -20, .4), (-30, 560, 150, 12, .32), (1640, 160, 210, 16, .4),
               (1760, 560, 150, -18, .32), (230, 470, 110, 26, .22), (1560, 470, 100, -24, .2)]


def sheets(kind):
    items = SHEETS_HERO if kind == "hero" else SHEETS_SIDE
    return '<div class="sheets">' + "".join(
        f'<span style="left:{x}px;top:{y}px;width:{w}px;opacity:{o};--r:{r}deg"></span>'
        for x, y, w, r, o in items) + '</div>'


def slide(body, section, kind="side"):
    SLIDES.append((body, section, kind))


def render():
    total = len(SLIDES)
    frames = []
    for index, (body, section, kind) in enumerate(SLIDES, start=1):
        segs = "".join(
            f'<span class="seg{" on" if s == section else ""}"><i>{n}</i>{s}</span>'
            for n, s in enumerate(SECTIONS, start=1))
        bar = (f'<header class="bar"><div class="brand"><span class="mark">{icon("doc_mark", 24)}</span>'
               f'<span>Документ <b>за 3 шага</b></span></div><nav class="segs">{segs}</nav>'
               f'<div class="count"><i></i>{index:02d} / {total:02d}</div></header>')
        foot = (f'<footer class="foot"><span>{URL}</span>'
                f'<span>Первенство России · продуктовое программирование · 2026</span></footer>')
        veil = '<div class="veil"></div>' if kind == "hero" else ""
        frames.append(
            f'<div class="frame"><div class="stage"><section class="slide {kind}">'
            f'{sheets(kind)}{veil}{bar}<div class="main">{body}</div>{foot}</section></div></div>')
    return "\n".join(frames)


def screen(src, alt, height, pos="top center"):
    return (f'<div class="screen" style="height:{height}px"><div class="sbar"><i></i><i></i><i></i>'
            f'<span>{URL}</span></div><img src="{src}" alt="{alt}" style="object-position:{pos}"></div>')


ROLES = ("<div class='roles'><span>Backend и API</span><span>Обработка текста и сверка фактов</span>"
         "<span>Генератор DOCX и оформление</span><span>Интерфейс</span><span>Проверки и сценарии</span></div>")

# 1 — титул в духе главной сервиса
slide(f'''
  <div class="hero-wrap">
    <div class="eyebrow pill-eyebrow">Первенство России · продуктовое программирование · кейс «Документ за 3 шага»</div>
    <h1 class="hero-title">Деловой документ<span>из вашего черновика.</span></h1>
    <p class="hero-lead">Письмо, записка или справка: от простого текста до оформленного файла Word за три шага.
    ИИ правит текст, программа держит оформление.</p>
    <div class="hero-actions"><span class="btn">{icon("file", 26)}{URL}</span>
      <span class="ghost">Команда Брянская область · БГИТУ</span></div>
    <div class="grid3 hero-steps">
      <div class="panel step-card"><div class="ico">{icon("file")}</div><h3>1. Добавьте текст</h3>
        <p>Напишите своими словами или вставьте готовый черновик.</p></div>
      <div class="panel step-card"><div class="ico">{icon("layers")}</div><h3>2. Укажите детали</h3>
        <p>Выберите тип документа, заполните реквизиты и оформление.</p></div>
      <div class="panel step-card"><div class="ico">{icon("check")}</div><h3>3. Скачайте документ</h3>
        <p>Проверьте результат и сохраните файл Word — его можно редактировать.</p></div>
    </div>
  </div>''', "Задача", "hero")

# 2 — проблема и цель
slide(f'''
  <div class="eyebrow">Проблема и цель</div>
  <h2>Документ без ручной вёрстки. <span>Текст — ИИ.</span></h2>
  <p class="lead">Сейчас текст правят в одном месте, оформление — в другом, а реквизиты вспоминают по памяти.
  Каждый круг исправлений съедает время.</p>
  <div class="body">
    <div class="grid3">
      <div class="panel"><div class="ico">{icon("alert")}</div><div class="k err">Проблема</div>
        <h3>Рутина с исправлениями</h3>
        <p>Текст вручную переносят в шаблон, настраивают шрифты и поля, отдельно проверяют орфографию
        и забывают обязательные реквизиты.</p></div>
      <div class="panel"><div class="ico">{icon("spark")}</div><div class="k good">Наш ответ</div>
        <h3>Разделили текст и форму</h3>
        <p>Модель исправляет ошибки и приводит текст к деловому стилю, не добавляя фактов.
        Шрифты, поля и колонтитулы применяет генератор по шаблону.</p></div>
      <div class="panel"><div class="ico">{icon("file")}</div><div class="k">Результат</div>
        <h3>Файл сразу по правилам</h3>
        <p>Редактируемый DOCX выбранного оформления. Чего не хватает — видно как
        «[Заполнить: …]», а не додумано.</p></div>
    </div>
    <div class="grid3">
      <div class="stat panel"><b class="num">3</b><span>шага от черновика до готового файла</span></div>
      <div class="stat panel"><b class="num">≈2 с</b><span>подготовка документа на рабочем стенде</span></div>
      <div class="stat panel"><b class="num">4 × 2</b><span>типа документов × оформления</span></div>
    </div>
  </div>''', "Задача")

# 3 — пользовательский сценарий
slide(f'''
  <div class="eyebrow">Пользовательский сценарий</div>
  <h2>Три шага. <span>Лист А4 всегда перед глазами.</span></h2>
  <div class="body">
    <div class="grid3 path">
      <div><div class="stepline"><i>1</i>Черновик</div>{screen(img("02-draft"), "Шаг 1: черновик", 400)}
        <p class="cap">Пишет или вставляет текст. Готовые примеры, в том числе черновик с опечатками.</p></div>
      <div><div class="stepline"><i>2</i>Тип и реквизиты</div>{screen(img("03-options"), "Шаг 2: тип и реквизиты", 400)}
        <p class="cap">Четыре типа и два оформления с превью. Реквизиты из черновика подставляются сами.</p></div>
      <div><div class="stepline"><i>3</i>Готовый файл</div>{screen(img("07-result-main"), "Шаг 3: готовый файл", 400)}
        <p class="cap">Список правок, пустые поля, правка прямо на листе и скачивание DOCX.</p></div>
    </div>
    <div class="pills">
      <span>Черновик сохраняется в браузере</span><span>Смена оформления — без повторного вызова модели</span>
      <span>Ctrl + Enter — дальше · Ctrl + S — скачать</span><span>Светлое и тёмное оформление</span>
    </div>
  </div>''', "Решение")

# 4 — было / стало
slide('''
  <div class="eyebrow">Демонстрация · сценарии 1 и 2</div>
  <h2>Из черновика — <span>в деловой текст.</span></h2>
  <p class="lead">Настоящий ответ стенда: докладная записка подготовлена за 1,8 секунды.</p>
  <div class="body">
    <div class="ba">
      <div class="panel">
        <div class="k err">Было · черновик</div>
<div class="raw">### СРОЧНО!!! докладная
Докладываю что <u>25.09.2026</u> в серверной была протечка.
<mark class="bad">темпиратура</mark> поднялась до <u>35 градусов</u>, <mark class="bad">УБЫТОК</mark> примерно <u>45 000 руб.</u>
<mark class="bad">- надо</mark> вызвать ремонт
<mark class="bad">- надо</mark> заменить <u>2 стойки</u>
<mark class="soft">подпись: Сидоров С.С.</mark></div>
      </div>
      <div class="arrow">→</div>
      <div class="paper sheet-doc">
        <div class="k paper-k">Стало · докладная записка</div>
        <div class="doc-title">ДОКЛАДНАЯ ЗАПИСКА</div>
        <div class="doc-sub">О протечке в серверной</div>
        <p>Докладываю, что <u>25.09.2026</u> в серверной произошла протечка.
        <mark class="good">Температура</mark> в помещении поднялась до <u>35 градусов</u>.
        <mark class="good">Убыток составил</mark> примерно <u>45 000 рублей</u>.</p>
        <p><mark class="good">Необходимо</mark> вызвать специалистов для проведения ремонта и заменить <u>две стойки</u>.</p>
        <div class="doc-sign">Сидоров С. С.</div>
      </div>
    </div>
    <div class="grid4">
      <div class="note"><i>1</i><span><b>Орфография.</b> «темпиратура» → «Температура»</span></div>
      <div class="note"><i>2</i><span><b>Стиль.</b> Капс и «надо» → деловые формулировки</span></div>
      <div class="note"><i>3</i><span><b>Реквизиты.</b> Подпись — в подписанта, тема — по смыслу</span></div>
      <div class="note"><i>4</i><span><b>Факты.</b> Дата, градусы, сумма и стойки — на месте</span></div>
    </div>
  </div>''', "Решение")

# 5 — защита фактов
slide(f'''
  <div class="eyebrow">Защита от выдумок · сценарий 4</div>
  <h2>Модель не может добавить факт. <span>Это проверяется.</span></h2>
  <p class="lead">Факты извлекаются из черновика отдельно от модели — сверять ответ с самим ответом нельзя.</p>
  <div class="body">
    <div class="fact-grid">
      <div class="timeline">
        <div class="tl"><div class="dot">{icon("search", 28)}</div><div class="panel">
          <h3>До модели</h3><p>Из черновика извлекаются даты, числа, фамилии и оговорки «если», «не позднее», «не».
          Разные записи сводятся к одному виду: «25.09.2026» = «25 сентября 2026», «30 000» = «тридцать тысяч».</p></div></div>
        <div class="tl"><div class="dot">{icon("brain", 28)}</div><div class="panel">
          <h3>Ответ модели</h3><p>Строгий JSON: реквизиты, абзацы текста, список правок. Схема проверяется до того,
          как ответ попадёт в документ.</p></div></div>
        <div class="tl"><div class="dot">{icon("shield", 28)}</div><div class="panel">
          <h3>Сверка</h3><p>Новый факт или сломанная схема — ровно один повтор с причиной. Неподтверждённый реквизит
          обнуляется и уходит в пропуски; пропавшие число, дата или оговорка дают предупреждение.</p></div></div>
      </div>
      <div class="col">
        <div class="panel"><div class="k good">Приоритет</div><h3>Ответ человека главнее модели</h3>
          <p>Введённый пользователем реквизит модель не перезаписывает. Инициалы сократить можно,
          раскрыть в полное имя — нельзя.</p></div>
        <div class="panel"><div class="k warn">Честно о границе</div><h3>Смысл проверяет человек</h3>
          <p>Сверка ловит числа, даты, фамилии и исчезнувшие оговорки, но не подмену смысла теми же словами.
          Поэтому список правок всегда показан перед скачиванием.</p></div>
      </div>
    </div>
  </div>''', "Решение")

# 6 — реквизиты и ошибки
slide(f'''
  <div class="eyebrow">Реквизиты и отказ модели · сценарии 3 и 6</div>
  <h2>Пропуск виден. <span>Текст не теряется.</span></h2>
  <p class="lead">Система не угадывает недостающее и не падает, если модель недоступна.</p>
  <div class="body">
    <div class="grid2">
      <div class="panel"><div class="ico">{icon("file")}</div><div class="k warn">Недостающие реквизиты</div>
        <h3>Спрашиваем или помечаем</h3>
        <ul><li>Обязательные поля заданы для каждого типа по перечню кейса</li>
          <li>Из черновика берутся подписанные строки: «Кому:», «Исх. № 12-45 от 11.09.2026» → номер и дата</li>
          <li>Адресата и подписанта из обычного текста не выводим — пустое поле честнее выдуманного</li>
          <li>Не заполнил — в файле <code>[Заполнить: Дата]</code>, заполнил — значение попадёт в документ</li></ul></div>
      <div class="panel"><div class="ico">{icon("plug")}</div><div class="k err">Если модель недоступна</div>
        <h3>Понятная причина и повтор</h3>
        <ul><li>Причина своими словами: модель не ответила вовремя, нет связи, ответ не по схеме</li>
          <li>Черновик и реквизиты остаются в форме и в браузере</li>
          <li>Повторить можно сразу, как только модель вернётся</li>
          <li>Без готового содержания файл не формируется — некорректный документ не уйдёт молча</li></ul></div>
    </div>
    <div class="warnbox">{icon("alert", 28)}<span><b>Остались пустыми: Кому, От кого, Дата, Номер.</b>
      Можно продолжить — в документе останутся метки.</span><em>так это видит пользователь</em></div>
  </div>''', "Решение")

# 7 — типы и оформления
slide(f'''
  <div class="eyebrow">Типы и шаблоны · сценарий 5</div>
  <h2>Тип — структура. <span>Шаблон — внешний вид.</span></h2>
  <p class="lead">Смена типа меняет набор реквизитов и порядок блоков, смена шаблона — только оформление.</p>
  <div class="body">
    <div class="types">
      <div class="panel table">
        <div class="tr th"><span>Тип документа</span><span>Обязательные реквизиты</span></div>
        <div class="tr"><b>Служебная записка</b><span>адресат, автор, дата, номер, заголовок, подпись</span></div>
        <div class="tr"><b>Докладная записка</b><span>адресат, автор, дата, номер, заголовок, подпись</span></div>
        <div class="tr"><b>Информационная справка</b><span>заголовок, дата, составитель</span></div>
        <div class="tr"><b>Письмо</b><span>адресат, отправитель, дата, номер, тема, подпись</span></div>
      </div>
      <div class="col">
        <div class="panel"><div class="k">Шаблон 1</div><h3>Классический корпоративный</h3>
          <p>Times New Roman 14 пт, интервал 1,5, адресат справа, организация в верхнем колонтитуле, номер страницы внизу</p></div>
        <div class="panel"><div class="k">Шаблон 2</div><h3>Современный регламентный</h3>
          <p>Arial 12 пт, интервал 1,15, «Кому / От кого» таблицей, подпись по центру, внизу название документа и дата</p></div>
      </div>
    </div>
    <div class="grid2">
      <div class="stat panel row"><b class="num sm">ГОСТ</b><span>Реквизиты по ГОСТ Р 7.0.97-2016 в упрощённом виде: дата и номер в одной строке</span></div>
      <div class="stat panel row"><b class="num sm">0</b><span>повторных обращений к модели при смене шаблона — содержание переиспользуется</span></div>
    </div>
  </div>''', "Решение")

# 8 — сверх минимума
slide(f'''
  <div class="eyebrow">Сверх обязательного минимума · сценарий 7</div>
  <h2>Правка на листе. <span>И своё оформление.</span></h2>
  <div class="body">
    <div class="extra">
      <div class="panel shot-panel"><div class="k good">Предпросмотр и правка</div>
        <h3>Редактирование прямо на листе</h3>
        <p>Режимы «Лист», «Текст», «Оформление». Шрифт, размер, начертание, выравнивание, интервал и отступ —
        над страницей, до скачивания.</p>
        {screen(img("07-result-main"), "Редактирование на листе", 470, "right top")}</div>
      <div class="col">
        <div class="panel shot-panel"><div class="k">Каталог</div><h3>Редактор оформления</h3>
          <p>Собственный шаблон: шрифт, поля, интервалы, выравнивание — с живым предпросмотром листа.</p>
          {screen(img("06-template-editor"), "Редактор оформления", 290, "left top")}</div>
        <div class="grid2 mini">
          <div class="panel tiny"><div class="ico">{icon("phone", 26)}</div><b>Телефон</b><span>шаги и лист — в колонку</span></div>
          <div class="panel tiny"><div class="ico">{icon("palette", 26)}</div><b>Две темы</b><span>светлая и тёмная</span></div>
        </div>
      </div>
    </div>
  </div>''', "Решение")

# 9 — архитектура
slide(f'''
  <div class="eyebrow">Архитектура</div>
  <h2>ИИ и оформление — <span>порознь.</span></h2>
  <p class="lead">Модель работает только с текстом и реквизитами — шрифты и поля ей не видны.</p>
  <div class="body">
    <div class="arch">
      <div class="panel node"><div class="ico">{icon("grid")}</div><h3>Браузер</h3><p class="tech">React · TypeScript · Vite</p><p>три шага, лист А4, черновик в localStorage</p></div>
      <div class="link"><span>POST /api/process</span><i></i><span>JSON · Request ID</span></div>
      <div class="panel node core"><div class="ico">{icon("server")}</div><h3>FastAPI</h3><p class="tech">Pydantic · кэш · лимит обработок</p><p>валидация, единый формат ошибок</p></div>
      <div class="link"><span>OpenAI-совместимый API</span><i></i><span>requisites · body · changes</span></div>
      <div class="panel node"><div class="ico">{icon("brain")}</div><h3>Обработчик текста</h3><p class="tech">модель + сверка фактов</p><p>один повтор, пропуски, предупреждения</p></div>
    </div>
    <div class="arch2">
      <div class="panel node wide"><div class="ico">{icon("layers")}</div><div><h3>YAML типов и оформлений</h3><p>реквизиты, порядок блоков, шрифты, поля, колонтитулы — проверяются при запуске</p></div></div>
      <div class="link"><span>POST /api/documents/download</span><i></i><span>без вызова модели</span></div>
      <div class="panel node wide"><div class="ico">{icon("file")}</div><div><h3>DOCX-генератор</h3><p class="tech">python-docx</p><p>редактируемые абзацы, кириллица, русский язык стилей</p></div></div>
    </div>
    <div class="grid3">
      <div class="panel mini-card"><div class="k">Модель</div><h3>Меняется в .env</h3><p>Локальная открытая модель или внешний провайдер — адрес и имя, без правки кода.</p></div>
      <div class="panel mini-card"><div class="k">Оформление</div><h3>Не решает ИИ</h3><p>Генератор получает готовое содержание и применяет шаблон программно.</p></div>
      <div class="panel mini-card"><div class="k">Проверяемость</div><h3>Тесты без сети</h3><p>Модель и DOCX за заменяемыми границами — проверки идут на подменённом клиенте.</p></div>
    </div>
  </div>''', "Устройство")

# 10 — стек
slide(f'''
  <div class="eyebrow">Стек технологий</div>
  <h2>Простой стек — <span>осознанно.</span></h2>
  <p class="lead">Запуск одной командой, проверка без ключей и без нашей помощи.</p>
  <div class="body">
    <div class="stackg">
      <div class="panel table stack">
        <div class="tr"><em>Backend</em><b>Python · FastAPI · Pydantic</b><span>контракты и валидация, OpenAPI и Swagger из коробки</span></div>
        <div class="tr"><em>Документ</em><b>python-docx</b><span>редактируемые абзацы, а не картинка страницы</span></div>
        <div class="tr"><em>ИИ</em><b>OpenAI-совместимый API</b><span>локальная модель через Ollama или провайдер — одна настройка</span></div>
        <div class="tr"><em>Интерфейс</em><b>React 19 · TypeScript · Vite</b><span>без UI-библиотек: своя дизайн-система и WebGL-заставка</span></div>
        <div class="tr"><em>Настройки</em><b>YAML</b><span>новый тип или шаблон — файл, а не релиз</span></div>
        <div class="tr"><em>Запуск</em><b>Docker Compose · nginx</b><span>интерфейс и API на одном адресе</span></div>
      </div>
      <div class="col">
        <div class="stat panel"><b class="num">{BUNDLE}</b><span>весь JavaScript интерфейса — без тяжёлых библиотек</span></div>
        <div class="stat panel"><b class="num">1</b><span>команда: <code>docker compose up --build</code></span></div>
        <div class="stat panel"><b class="num">0</b><span>ключей для первого запуска — сквозной путь работает без модели</span></div>
      </div>
    </div>
  </div>''', "Устройство")

# 11 — готовность
slide(f'''
  <div class="eyebrow">Готовность</div>
  <h2>6 из 6 обязательных сценариев. <span>Плюс седьмой.</span></h2>
  <div class="body">
    <div class="ready">
      <div class="panel checklist">
        <div class="ck"><i>1</i><div><h4>Полный путь до DOCX</h4><small>обязательный</small></div><span>черновик, тип, шаблон, файл открывается в Word</span><em>{icon("check", 22)}</em></div>
        <div class="ck"><i>2</i><div><h4>Орфография и стиль</h4><small>обязательный</small></div><span>опечатки и разговорные обороты исправлены</span><em>{icon("check", 22)}</em></div>
        <div class="ck"><i>3</i><div><h4>Недостающие реквизиты</h4><small>обязательный</small></div><span>пропуск виден, введённое значение — в файле</span><em>{icon("check", 22)}</em></div>
        <div class="ck"><i>4</i><div><h4>Факты и смысл</h4><small>обязательный</small></div><span>даты, суммы, фамилии и условия сверяются</span><em>{icon("check", 22)}</em></div>
        <div class="ck"><i>5</i><div><h4>Типы и шаблоны</h4><small>обязательный</small></div><span>4 типа, 2 оформления одного текста</span><em>{icon("check", 22)}</em></div>
        <div class="ck"><i>6</i><div><h4>Отказ модели</h4><small>обязательный</small></div><span>понятное сообщение, текст сохранён, повтор</span><em>{icon("check", 22)}</em></div>
        <div class="ck extra-row"><i>7</i><div><h4>Предпросмотр и правка</h4><small class="add">дополнительный</small></div><span>правка текста и оформления на листе до скачивания</span><em>{icon("check", 22)}</em></div>
      </div>
      <div class="col">
        <div class="panel qr"><div class="k good">Проверка без команды</div><h3>Откройте и соберите документ</h3>
          <div class="qr-row"><img src="{qr()}" alt="QR-код стенда"><div><b>{URL}</b><p>Регистрация не нужна. Готовые примеры, включая черновик с опечатками.</p></div></div></div>
        <div class="panel facts">
          <p>{icon("check", 22)}<span><b>{TESTS} автотестов</b> — API, сверка фактов, DOCX обоих шаблонов</span></p>
          <p>{icon("check", 22)}<span><b>Swagger и OpenAPI</b> — каждый запрос проверяется без интерфейса</span></p>
          <p>{icon("check", 22)}<span><b>README</b> — запуск, настройки, добавление типа и шаблона</span></p>
        </div>
      </div>
    </div>
  </div>''', "Готовность")

# 12 — развитие
slide(f'''
  <div class="eyebrow">Масштабирование и развитие</div>
  <h2>Растём без переписывания. <span>Границы уже выделены.</span></h2>
  <div class="body">
    <div class="grid2 growth">
      <div class="panel g"><div class="ico">{icon("plus")}</div><div><div class="k good">Уже работает</div><h3>Новый тип документа</h3>
        <p>Один YAML-файл: поля, обязательность, порядок блоков. Форма и генератор подхватывают его сами.</p></div></div>
      <div class="panel g"><div class="ico">{icon("building")}</div><div><div class="k good">Уже работает · дальше</div><h3>Корпоративные шаблоны</h3>
        <p>Своё оформление собирается в редакторе каталога. Следующий шаг — разбор загруженного DOCX организации.</p></div></div>
      <div class="panel g"><div class="ico">{icon("link")}</div><div><div class="k">Следующий шаг</div><h3>Интеграция с СЭД</h3>
        <p>Подготовка и выдача DOCX — отдельные вызовы API с опубликованным контрактом OpenAPI. СЭД подключается как клиент.</p></div></div>
      <div class="panel g"><div class="ico">{icon("rocket")}</div><div><div class="k">Следующий шаг</div><h3>Нагрузка</h3>
        <p>Уже есть кэш результата и лимит одновременных обработок. Дальше — общий кэш и несколько копий backend.</p></div></div>
    </div>
    <div class="panel closing">ИИ правит текст, <span>программа держит форму,</span> факты сверяются с черновиком.</div>
  </div>''', "Готовность")

# 13 — спасибо
slide(f'''
  <div class="hero-wrap thanks">
    <div class="eyebrow pill-eyebrow">Спасибо за внимание</div>
    <h1 class="hero-title">Готовы показать<span>всё вживую.</span></h1>
    <div class="thanks-row">
      <div class="panel qr big"><img src="{qr()}" alt="QR-код стенда"><div><b>{URL}</b>
        <p>Отсканируйте и соберите документ сами — регистрация не нужна.</p></div></div>
      <div class="panel team"><div class="k">Команда Брянская область · БГИТУ</div>{ROLES}</div>
    </div>
  </div>''', "Готовность", "hero")


CSS = r'''
:root{
  --bg:#0a0b0d; --bg-deep:#08090b; --line:rgba(255,255,255,.11); --line2:rgba(255,255,255,.22);
  --panel:linear-gradient(150deg,rgba(25,28,33,.95),rgba(17,19,23,.93));
  --text:#edeef0; --text2:#a3a8af; --text3:#757b84; --accent:#e9ebee; --ink:#0b0c0e;
  --warn:#d3ad74; --warn-soft:rgba(211,173,116,.12); --error:#dd8d86; --error-soft:rgba(221,141,134,.12);
  --good:#93c2aa; --good-soft:rgba(147,194,170,.12); --paper:#ffffff; --paper-ink:#101214;
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI Variable Display","Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
  /* ui-monospace при печати в PDF не находится и падает в Times — поэтому конкретные шрифты. */
  --mono:Menlo,"SF Mono",Monaco,Consolas,"Liberation Mono","Courier New",monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#050506;font-family:var(--font);color:var(--text)}
.stage{width:1920px;height:1080px;transform-origin:top left;transform:scale(var(--k,1))}
.frame{margin:0 auto 28px;width:calc(1920px * var(--k,1));height:calc(1080px * var(--k,1));overflow:hidden}
.slide{position:relative;width:1920px;height:1080px;overflow:hidden;padding:0 100px;display:flex;flex-direction:column;
  -webkit-font-smoothing:antialiased;
  background:
    radial-gradient(ellipse at 50% 6%,rgba(146,158,180,.11),transparent 58%),
    radial-gradient(rgba(255,255,255,.05) 1.2px,transparent 1.4px) 0 0/30px 30px,
    linear-gradient(180deg,var(--bg-deep),var(--bg))}
/* Зерно, как на сайте: снимает полосы на больших плоских заливках. */
.slide::after{content:"";position:absolute;inset:0;z-index:5;pointer-events:none;opacity:.06;mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");background-size:140px}
.sheets{position:absolute;inset:0;z-index:0;pointer-events:none}
.sheets span{position:absolute;aspect-ratio:210/297;border-radius:2px 10px 3px 2px;transform:rotate(var(--r));
  background:repeating-linear-gradient(180deg,transparent 0 9px,#626975 9px 10px) center/66% 56% no-repeat,
    linear-gradient(115deg,#c4cbd5,#f5f5f3 56%,#a8b0bc);box-shadow:2px 8px 26px rgba(0,0,0,.4)}
.veil{position:absolute;inset:0;z-index:0;pointer-events:none;
  background:radial-gradient(ellipse 42% 46% at 50% 44%,rgba(10,11,13,.9),rgba(10,11,13,.55) 62%,transparent 100%)}
.slide>.bar,.slide>.main,.slide>.foot{position:relative;z-index:1}

.bar{height:66px;margin-top:34px;display:flex;align-items:center;justify-content:space-between;flex:none}
.brand{display:flex;align-items:center;gap:14px;font-size:24px;color:var(--text2);letter-spacing:-.01em}
.brand b{color:var(--text);font-weight:600}
.mark{width:46px;height:46px;border-radius:13px;display:grid;place-items:center;color:var(--text);
  background:linear-gradient(150deg,#2b2f36,#15171b);border:1px solid var(--line2)}
.segs{display:flex;gap:4px;padding:5px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.03)}
.seg{display:flex;align-items:center;gap:10px;padding:9px 22px 9px 10px;border-radius:999px;font-size:19px;color:var(--text3)}
.seg i{font-style:normal;width:28px;height:28px;border-radius:50%;border:1px solid var(--line2);display:grid;place-items:center;font-size:14px}
.seg.on{background:rgba(255,255,255,.09);color:var(--text)}
.seg.on i{background:var(--accent);color:var(--ink);border-color:transparent;font-weight:600}
.count{display:flex;align-items:center;gap:12px;padding:10px 20px;border:1px solid var(--line);border-radius:999px;
  font-size:19px;color:var(--text2);font-variant-numeric:tabular-nums}
.count i{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px rgba(255,255,255,.08)}
.foot{height:58px;flex:none;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;
  font-size:18px;color:var(--text3)}

.main{flex:1;display:flex;flex-direction:column;min-height:0;padding:38px 0 24px}
.eyebrow{font-size:19px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--text3)}
h2{margin:16px 0 0;font-size:70px;font-weight:680;letter-spacing:-.045em;line-height:1.02;white-space:nowrap}
h2 span{color:var(--text2);font-weight:400}
.lead{margin:16px 0 0;font-size:27px;line-height:1.5;color:var(--text2);max-width:1520px}
.body{flex:1;display:flex;flex-direction:column;justify-content:center;gap:24px;min-height:0;padding-top:24px}
h3{margin:0 0 8px;font-size:30px;font-weight:620;letter-spacing:-.022em;line-height:1.15;color:var(--text)}
p,li{font-size:22px;line-height:1.5;color:var(--text2);margin:0 0 6px}
ul{margin:4px 0 0;padding-left:24px} li{margin-bottom:8px}
b{color:var(--text);font-weight:600}
code{font-family:var(--mono);font-size:.88em;background:rgba(255,255,255,.06);border:1px solid var(--line);border-radius:8px;padding:2px 8px;color:var(--text)}

.panel{background:var(--panel);border:1px solid var(--line);border-radius:28px;padding:28px 32px;
  box-shadow:0 1px 0 rgba(255,255,255,.04) inset,0 34px 60px -40px rgba(0,0,0,.95)}
.k{font-size:16px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--text3);margin:0 0 10px}
.k.good{color:var(--good)} .k.warn{color:var(--warn)} .k.err{color:var(--error)}
.ico{width:56px;height:56px;border-radius:16px;border:1px solid var(--line2);background:rgba(255,255,255,.05);
  display:grid;place-items:center;margin-bottom:16px;color:var(--text);flex:none}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.col{display:flex;flex-direction:column;gap:24px}
.stat{padding:22px 30px}
.num{display:block;font-size:76px;font-weight:680;letter-spacing:-.05em;line-height:1;color:var(--text)}
.num.sm{font-size:56px}
.stat span{display:block;font-size:21px;color:var(--text3);margin-top:10px}
.stat.row{display:flex;align-items:center;gap:26px}
.stat.row span{margin:0;font-size:21px}
.screen{border:1px solid var(--line2);border-radius:20px;overflow:hidden;background:#0d0e11;display:flex;flex-direction:column;
  box-shadow:0 40px 80px -50px rgba(0,0,0,.9)}
.sbar{flex:none;display:flex;align-items:center;gap:8px;padding:10px 16px;border-bottom:1px solid var(--line)}
.sbar i{width:11px;height:11px;border-radius:50%;background:rgba(255,255,255,.16)}
.sbar span{margin-left:10px;font-size:15px;color:var(--text3);border:1px solid var(--line);border-radius:999px;padding:2px 14px}
.screen img{flex:1;min-height:0;width:100%;object-fit:cover;display:block}

/* 1 и 13 — как главная сервиса */
.hero .main{padding-top:10px}
.hero-wrap{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.pill-eyebrow{border:1px solid var(--line);border-radius:999px;padding:10px 22px;background:rgba(10,11,13,.6)}
.hero-title{margin:26px 0 0;font-size:118px;font-weight:680;letter-spacing:-.05em;line-height:.98;text-shadow:0 2px 40px rgba(0,0,0,.45)}
.hero-title span{display:block;color:var(--text2);font-weight:400}
.hero-lead{margin:26px 0 0;max-width:1080px;font-size:28px;line-height:1.55;color:var(--text2)}
.hero-actions{display:flex;align-items:center;gap:26px;margin-top:34px}
.btn{display:inline-flex;align-items:center;gap:12px;background:var(--accent);color:var(--ink);border-radius:999px;padding:16px 32px;font-size:25px;font-weight:600}
.ghost{font-size:21px;color:var(--text3)}
.hero-steps{width:1500px;margin-top:52px;text-align:center}
.step-card{padding:26px 28px;background:linear-gradient(150deg,rgba(25,28,33,.86),rgba(17,19,23,.84))}
.step-card .ico{margin:0 auto 14px}
.step-card p{font-size:21px;margin:0}

/* 3 */
.path{gap:30px}
.stepline{display:flex;align-items:center;gap:14px;font-size:26px;font-weight:600;margin-bottom:16px;color:var(--text)}
.stepline i{font-style:normal;width:36px;height:36px;border-radius:50%;background:var(--accent);color:var(--ink);display:grid;place-items:center;font-size:18px}
.cap{margin-top:16px;font-size:21px}
.pills{display:flex;flex-wrap:wrap;gap:12px}
.pills span{border:1px solid var(--line);border-radius:999px;padding:10px 20px;font-size:19px;color:var(--text2);background:rgba(255,255,255,.03)}

/* 4 */
.ba{display:grid;grid-template-columns:1fr 70px 1fr;align-items:stretch}
.arrow{display:grid;place-items:center;font-size:56px;color:var(--text3)}
.raw{white-space:pre-wrap;font-family:var(--mono);font-weight:500;font-size:22px;line-height:1.62;color:var(--text)}
.raw u,.sheet-doc u{white-space:nowrap}
mark.bad{background:var(--error-soft);color:#f0b9b3;border-radius:6px;padding:0 5px}
mark.soft{background:rgba(255,255,255,.08);color:var(--text);border-radius:6px;padding:0 5px}
u{text-decoration:none;border-bottom:2px solid rgba(211,173,116,.8)}
.paper{background:var(--paper);color:var(--paper-ink);border-radius:8px;
  box-shadow:0 40px 80px -50px rgba(0,0,0,.8),0 4px 16px -10px rgba(0,0,0,.55)}
.sheet-doc{padding:30px 44px;font:400 23px/1.55 "Times New Roman",Times,serif}
.paper-k{font-family:var(--font);color:#6b7078}
.doc-title{text-align:center;font-weight:700;letter-spacing:.03em;margin:4px 0 8px}
.doc-sub{font-weight:700;margin-bottom:8px}
.sheet-doc p{font:inherit;color:inherit;text-indent:1.2em;text-align:justify;margin:0 0 8px}
.sheet-doc b{color:inherit}
mark.good{background:rgba(34,108,82,.13);color:#1d5c46;border-radius:5px;padding:0 4px}
.sheet-doc u{border-bottom-color:rgba(160,110,30,.7)}
.doc-sign{text-align:right;margin-top:12px}
.note{display:flex;align-items:center;gap:14px;border:1px solid var(--line);border-radius:18px;padding:14px 18px;background:rgba(255,255,255,.03)}
.note i{flex:none;font-style:normal;width:36px;height:36px;border-radius:50%;border:1px solid var(--line2);display:grid;place-items:center;font-size:17px;color:var(--text)}
.note span{font-size:19px;line-height:1.35;color:var(--text2)}

/* 5 */
.fact-grid{display:grid;grid-template-columns:1.35fr 1fr;gap:28px;align-items:start}
.timeline{display:flex;flex-direction:column;gap:18px;position:relative}
.timeline::before{content:"";position:absolute;left:35px;top:40px;bottom:40px;border-left:1px dashed var(--line2)}
.tl{display:grid;grid-template-columns:72px 1fr;gap:20px;align-items:center}
.tl .dot{width:72px;height:72px;border-radius:50%;border:1px solid var(--line2);background:#111317;display:grid;place-items:center;color:var(--text);z-index:1}
.tl .panel{padding:20px 26px}
.tl p{margin:0}

/* 6 */
.warnbox{display:flex;align-items:center;gap:16px;background:var(--warn-soft);border:1px solid rgba(211,173,116,.3);
  border-radius:20px;padding:18px 24px;color:var(--warn)}
.warnbox span{font-size:22px;color:#e9d6b8}
.warnbox b{color:#f6e6cc}
.warnbox em{margin-left:auto;font-style:normal;font-size:17px;color:var(--text3);white-space:nowrap}

/* 7 */
.types{display:grid;grid-template-columns:1.25fr 1fr;gap:24px}
.table{padding:8px 32px}
.tr{display:grid;grid-template-columns:330px 1fr;gap:20px;padding:17px 0;border-bottom:1px solid var(--line);align-items:center}
.tr:last-child{border-bottom:none}
.tr.th span{font-size:15px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--text3)}
.tr b{font-size:25px;font-weight:600}
.tr span{font-size:21px;color:var(--text2)}
.types .col .panel p{margin:0}

/* 8 */
.extra{display:grid;grid-template-columns:1.1fr 1fr;gap:24px;align-items:stretch}
.shot-panel{display:flex;flex-direction:column}
.shot-panel p{margin-bottom:16px}
.shot-panel .screen{flex:none}
.mini{gap:18px}
.tiny{display:flex;align-items:center;gap:16px;padding:18px 22px}
.tiny .ico{margin:0;width:48px;height:48px}
.tiny b{display:block;font-size:22px}
.tiny span{display:block;font-size:18px;color:var(--text3)}

/* 9 */
.arch{display:grid;grid-template-columns:1fr 230px 1fr 230px 1fr;align-items:center}
.arch2{display:grid;grid-template-columns:1fr 320px 1fr;align-items:center}
.node{padding:18px 22px;text-align:center}
.node .ico{margin:0 auto 10px;width:50px;height:50px}
.node h3{font-size:27px;margin-bottom:2px}
.node p{font-size:19px;margin:0}
.node .tech{color:var(--text);margin-bottom:2px}
.node.core{border-color:var(--line2);background:linear-gradient(150deg,rgba(38,42,49,.95),rgba(22,24,29,.93))}
.node.wide{display:flex;gap:18px;align-items:center;text-align:left}
.node.wide .ico{margin:0}
.link{display:flex;flex-direction:column;align-items:center;gap:8px;padding:0 10px}
.link i{display:block;width:100%;border-top:1px dashed var(--line2);position:relative}
.link i::after{content:"";position:absolute;right:-2px;top:-5px;width:9px;height:9px;border-top:1px solid var(--text2);border-right:1px solid var(--text2);transform:rotate(45deg)}
.link span{font-family:var(--mono);font-weight:500;font-size:15px;line-height:1.2;color:var(--text2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;background:rgba(255,255,255,.03);text-align:center}
.mini-card{padding:18px 24px}
.mini-card h3{font-size:25px}
.mini-card p{font-size:19px;margin:0}

/* 10 */
.stackg{display:grid;grid-template-columns:1.55fr 1fr;gap:24px}
.stack .tr{grid-template-columns:150px 390px 1fr;padding:15px 0}
.stack .tr em{font-style:normal;font-size:14px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--text3)}
.stack .tr b{font-size:23px}

/* 11 */
.ready{display:grid;grid-template-columns:1.5fr 1fr;gap:24px}
.checklist{padding:6px 30px}
.ck{display:grid;grid-template-columns:52px 320px 1fr 40px;gap:16px;align-items:center;padding:13px 0;border-bottom:1px solid var(--line)}
.ck:last-child{border-bottom:none}
.ck>i{font-style:normal;width:40px;height:40px;border-radius:50%;border:1px solid var(--line2);display:grid;place-items:center;font-size:18px;color:var(--text)}
.ck h4{margin:0;font-size:23px;font-weight:600;letter-spacing:-.01em}
.ck small{font-size:13px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--good)}
.ck small.add{color:var(--warn)}
.ck span{font-size:19px;color:var(--text2);line-height:1.35}
.ck em{width:38px;height:38px;border-radius:50%;background:var(--good-soft);border:1px solid rgba(147,194,170,.4);color:var(--good);display:grid;place-items:center}
.extra-row{background:linear-gradient(90deg,rgba(211,173,116,.06),transparent)}
.qr h3{font-size:27px}
.qr-row{display:flex;gap:22px;align-items:center;margin-top:8px}
.qr-row img,.qr.big img{width:170px;height:170px;border-radius:14px;padding:8px;background:#fff}
.qr-row b{font-size:26px} .qr-row p{font-size:19px;margin-top:6px}
.facts p{display:flex;gap:12px;align-items:flex-start;font-size:20px;margin:0 0 12px}
.facts p:last-child{margin:0}
.facts svg{flex:none;color:var(--good);margin-top:4px}

/* 12 */
.growth{gap:22px}
.g{display:flex;gap:22px;align-items:flex-start;padding:24px 28px}
.g .ico{margin:0}
.g p{margin:0}
.closing{text-align:center;font-size:36px;font-weight:600;letter-spacing:-.02em;padding:24px;color:var(--text)}
.closing span{color:var(--text2);font-weight:400}

/* 13 */
.thanks .hero-title{font-size:104px}
.thanks-row{display:grid;grid-template-columns:auto 820px;gap:24px;margin-top:48px;text-align:left;align-items:center}
.team{align-self:stretch;display:flex;flex-direction:column;justify-content:center}
.qr.big{display:flex;align-items:center;gap:26px;padding:26px 32px}
.qr.big img{width:200px;height:200px}
.qr.big b{font-size:34px} .qr.big p{font-size:21px;margin-top:8px}
.team{padding:24px 30px}
.roles{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
.roles span{border:1px solid var(--line);border-radius:999px;padding:9px 18px;font-size:19px;color:var(--text2);background:rgba(255,255,255,.03)}

@page{size:1920px 1080px;margin:0}
@media print{
  html,body{background:#050506}
  /* Шум с режимом наложения заставляет печать растрировать страницу целиком:
     PDF распухал до 48 МБ. На экране зерно остаётся, в файле — нет. */
  .slide::after{display:none}
  .frame{width:1920px;height:1080px;margin:0;page-break-after:always;break-after:page}
  .frame:last-child{page-break-after:auto}
  .stage{transform:none}
}
'''

FIT = '''<script>
(function(){
  function fit(){
    var k = Math.min(1, (window.innerWidth - 32) / 1920);
    document.documentElement.style.setProperty('--k', k.toFixed(4));
  }
  window.addEventListener('resize', fit);
  fit();
})();
</script>'''

PAGE = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<title>Документ за 3 шага — презентация</title>'
        '<style>__CSS__</style></head><body>__SLIDES__' + FIT + '</body></html>')

OUT.mkdir(parents=True, exist_ok=True)
html = PAGE.replace("__CSS__", CSS).replace("__SLIDES__", render())
(OUT / "presentation.html").write_text(html, encoding="utf-8")
print("слайдов:", len(SLIDES), "| размер HTML:", len(html) // 1024, "КБ")
