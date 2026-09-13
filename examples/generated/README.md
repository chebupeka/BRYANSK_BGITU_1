# Сгенерированные документы

Готовые DOCX для черновиков из [examples/drafts](../drafts): 20 черновиков разного качества
(размеченные, разговорные, неполные, сплошным текстом, пограничные) и 24 документа — каждый
черновик в оформлении «classic», а первый черновик каждого типа ещё и в «modern».

Документы получены 13.09.2026 на стенде https://doc3.codeboom.pro в режиме обработки `llm`
тем же путём, что проходит пользователь в интерфейсе: подсказка реквизитов из черновика,
обработка текста, выгрузка DOCX. Реквизиты вручную не дописывались: всё, чего сервис не
нашёл в черновике, осталось в документе меткой «[Заполнить: …]».

## Что проверено

Каждый файл открыт через python-docx (текст абзацев, таблиц и колонтитулов) и сверен
с [manifest.yaml](../drafts/manifest.yaml):

- все 24 файла открываются, текст непустой;
- значения из `must_keep` (даты, суммы, номера, фамилии, адреса почты) найдены в 23 файлах
  из 24; сравнение без учёта регистра и пробелов внутри чисел;
- для каждого обязательного реквизита из `not_in_draft` в документе стоит метка
  «[Заполнить: …]», ни одно значение не подставлено;
- разговорные обороты и опечатки из черновиков («Вообщем», «Здрасьте», «компа», «барахлит»,
  «испортится», «темпиратура», «СРОЧНО!!!», решётки markdown, двойные пробелы) в документах
  отсутствуют.

Исключение — `edge_04_number_formats.docx`: даты «31.03.2025» и «15.03.2025» переписаны как
«31 марта 2025 года» и «15 марта 2025 года». Сами даты не изменились, но форма записи
отличается от черновика, а предупреждения сервис не выдал.

## Документы

Оформление «classic»: Times New Roman, адресат блоком справа, организация в верхнем
колонтитуле, номер страницы внизу. «modern»: Arial, адресат и автор таблицей
«Кому | значение», в нижнем колонтитуле «Тип документа от даты».

| Черновик | Документ | Тип | Оформление | На что смотреть |
|---|---|---|---|---|
| [service_memo_01_structured](../drafts/service_memo_01_structured.txt) | [service_memo_01_structured.docx](service_memo_01_structured.docx) | Служебная записка | classic | Все реквизиты заполнены из черновика, меток нет. «может привезти» → «готов осуществить поставку». Сервис предупредил, что пропало «без» («без простоев» стало «бесперебойной работы») |
| [service_memo_01_structured](../drafts/service_memo_01_structured.txt) | [service_memo_01_structured.modern.docx](service_memo_01_structured.modern.docx) | Служебная записка | modern | Тот же текст и реквизиты: сравнить с classic расположение адресата, шрифт и колонтитулы |
| [service_memo_02_colloquial](../drafts/service_memo_02_colloquial.txt) | [service_memo_02_colloquial.docx](service_memo_02_colloquial.docx) | Служебная записка | classic | Реквизиты без двоеточий («Дата 12.03.2025») распознаны. Убраны «Здрасьте», «компа», «Вообщем»; «180000» записано как «180 000». Фраза «Без этого мы не сможем делать задачи в срок» в документ не вошла — сервис выдал предупреждение о пропавших отрицаниях. Подписант — «Петров», без инициалов, как в черновике |
| [service_memo_03_incomplete](../drafts/service_memo_03_incomplete.txt) | [service_memo_03_incomplete.docx](service_memo_03_incomplete.docx) | Служебная записка | classic | Нет адресата, даты и номера — в документе метки «[Заполнить: Кому]», «[Заполнить: Дата]», «[Заполнить: Номер]» |
| [service_memo_04_flat](../drafts/service_memo_04_flat.txt) | [service_memo_04_flat.docx](service_memo_04_flat.docx) | Служебная записка | classic | Текст переведён от первого лица («Сообщаю, что…»). Из сплошного абзаца взяты только подписант и тема; автор и дата остались метками, хотя названы в тексте, — дата «12.03.2025» сохранена в тексте как дата события |
| [report_memo_01_structured](../drafts/report_memo_01_structured.txt) | [report_memo_01_structured.docx](report_memo_01_structured.docx) | Докладная записка | classic | Меток нет. Сохранены адрес склада и обе даты. Организация отдельным реквизитом не выделена — она остаётся в строке адресата |
| [report_memo_01_structured](../drafts/report_memo_01_structured.txt) | [report_memo_01_structured.modern.docx](report_memo_01_structured.modern.docx) | Докладная записка | modern | Адресат и автор таблицей, в колонтитуле «Докладная записка от 14.03.2025» |
| [report_memo_02_colloquial](../drafts/report_memo_02_colloquial.txt) | [report_memo_02_colloquial.docx](report_memo_02_colloquial.docx) | Докладная записка | classic | «Там всё плохо» → «В ходе проверки выявлены следующие недостатки», «барахлит» и «испортится» убраны. В черновике «Подпись Николаева.» без инициалов — подписант не подставлен, стоит «[Заполнить: Подписант]» |
| [report_memo_03_incomplete](../drafts/report_memo_03_incomplete.txt) | [report_memo_03_incomplete.docx](report_memo_03_incomplete.docx) | Докладная записка | classic | Метки «Кому», «Дата», «Номер». Организация необязательна и в документ не выводится |
| [report_memo_04_flat](../drafts/report_memo_04_flat.txt) | [report_memo_04_flat.docx](report_memo_04_flat.docx) | Докладная записка | classic | Даты 10–13 марта и 01.04.2025 относятся к событию и не взяты датой документа — метка «[Заполнить: Дата]». Автор тоже остался меткой, подписант заполнен |
| [information_note_01_structured](../drafts/information_note_01_structured.txt) | [information_note_01_structured.docx](information_note_01_structured.docx) | Информационная справка | classic | Меток нет. Сохранены три даты, «24 сотрудника» и «92 процента». Подписант — «руководитель отдела развития Козлов К.К.» |
| [information_note_01_structured](../drafts/information_note_01_structured.txt) | [information_note_01_structured.modern.docx](information_note_01_structured.modern.docx) | Информационная справка | modern | Колонтитул «Информационная справка от 15.03.2025»; таблицы адресата нет, потому что у справки адресат необязателен |
| [information_note_02_colloquial](../drafts/information_note_02_colloquial.txt) | [information_note_02_colloquial.docx](information_note_02_colloquial.docx) | Информационная справка | classic | Убраны «Вообщем», «сделал много», «это нормально», «доделаем»; «утвердили» → «был утверждён». Все числа и даты на месте |
| [information_note_03_incomplete](../drafts/information_note_03_incomplete.txt) | [information_note_03_incomplete.docx](information_note_03_incomplete.docx) | Информационная справка | classic | Даты документа нет — «[Заполнить: Дата]»; дата «31.03.2025» из текста не использована как дата справки |
| [information_note_04_flat](../drafts/information_note_04_flat.txt) | [information_note_04_flat.docx](information_note_04_flat.docx) | Информационная справка | classic | Один абзац разбит на четыре. Должность и фамилия вынесены в подпись, «По состоянию на 15.03.2025» осталось в тексте, дата справки — метка |
| [letter_01_structured](../drafts/letter_01_structured.txt) | [letter_01_structured.docx](letter_01_structured.docx) | Письмо | classic | Меток нет. Заполнены обращение и исполнитель с телефоном, организация в верхнем колонтитуле. Сохранены адрес почты и количества |
| [letter_01_structured](../drafts/letter_01_structured.txt) | [letter_01_structured.modern.docx](letter_01_structured.modern.docx) | Письмо | modern | Колонтитул «Письмо от 16.03.2025», адресат таблицей |
| [letter_02_colloquial](../drafts/letter_02_colloquial.txt) | [letter_02_colloquial.docx](letter_02_colloquial.docx) | Письмо | classic | «Мы хотим заключить» → «выражает заинтересованность в заключении договора», «Пришлите пожалуйста» и «Будем рады» убраны. Тема переформулирована: «О заключении договора на поставку мебели». Кавычки вокруг «Ромашка» не восстановлены |
| [letter_03_incomplete](../drafts/letter_03_incomplete.txt) | [letter_03_incomplete.docx](letter_03_incomplete.docx) | Письмо | classic | Метки «[Заполнить: Адресат]» и «[Заполнить: Исходящий номер]»: имя из обращения «Фёдор Фёдорович» адресатом не подставлено |
| [letter_04_flat](../drafts/letter_04_flat.txt) | [letter_04_flat.docx](letter_04_flat.docx) | Письмо | classic | Метки «Организация отправителя» (в колонтитуле), «Адресат», «Дата», «Исходящий номер»; срок ответа 25.03.2025 датой письма не стал. Неточность: адрес почты назван «Контактное лицо» |
| [edge_01_single_line](../drafts/edge_01_single_line.txt) | [edge_01_single_line.docx](edge_01_single_line.docx) | Служебная записка | classic | Одна строка без знаков препинания разбита на предложения с заглавными буквами. «ответственный Петров П.П.» записан исполнителем, поэтому подписант, как и адресат, автор, дата и номер, остался меткой |
| [edge_02_typos_and_noise](../drafts/edge_02_typos_and_noise.txt) | [edge_02_typos_and_noise.docx](edge_02_typos_and_noise.docx) | Докладная записка | classic | «темпиратура» исправлена, «СРОЧНО!!!», решётки, дефисы списка и двойные пробелы убраны, «2 стойки» → «две стойки». Тема выведена по смыслу: «О протечке в серверной» |
| [edge_03_mixed_alphabets](../drafts/edge_03_mixed_alphabets.txt) | [edge_03_mixed_alphabets.docx](edge_03_mixed_alphabets.docx) | Письмо | classic | Латиница оставлена как есть: «CEO» в адресате, «Equipment delivery» в теме, «120 000 RUB». Организация не выделена из строки адресата — метка в колонтитуле; дата и номер — метки |
| [edge_04_number_formats](../drafts/edge_04_number_formats.txt) | [edge_04_number_formats.docx](edge_04_number_formats.docx) | Информационная справка | classic | Сумма прописью, «92,5 процента» и «250000» → «250 000» сохранены. Даты «31.03.2025» и «15.03.2025» переписаны словами (см. «Что проверено»). Дата справки — метка |

## Как перегенерировать

Скрипт [scripts/generate_examples.py](../../scripts/generate_examples.py) использует только
стандартную библиотеку Python. Из корня репозитория:

```bash
# локальный сервис (docker compose up --build), адрес по умолчанию http://localhost:8080
python3 scripts/generate_examples.py

# другой адрес; --responses сохраняет ответы /api/process в JSON для разбора
python3 scripts/generate_examples.py https://doc3.codeboom.pro --responses /tmp/responses
```

Для каждого случая из `manifest.yaml` скрипт вызывает `POST /api/requisites/suggest`,
затем `POST /api/process` с подсказанными реквизитами и `POST /api/documents/download`
с оформлением `classic` (для первого черновика каждого типа — ещё `modern`), и перезаписывает
файлы в этом каталоге. Между вызовами `/api/process` выдерживается пауза 3,5 секунды;
ответы 429 и 503 и обрывы соединения повторяются через 20 секунд.

Текст меняется только в режиме обработки `llm` (`TEXT_PROCESSOR=llm`); с настройкой по
умолчанию `stub` документы получатся, но без правки текста. Ответ модели может отличаться
от запуска к запуску, поэтому после перегенерации таблицу выше нужно сверить заново.
