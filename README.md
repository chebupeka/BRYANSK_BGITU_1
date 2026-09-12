# Документ за 3 шага

Черновик → тип документа и реквизиты → редактируемый DOCX. Рабочая часть роли 1: FastAPI, стабильный API, OpenAI-совместимый транспорт LLM, конфигурация, ограниченный кэш, Docker Compose и точки подключения модулей команды.

**Начните с [инструкции для роли 1](docs/ROLE_1.md).** Подключение остальных участников: [HANDOFF.md](docs/HANDOFF.md). Запросы и ошибки: [API.md](docs/API.md). Схема приложения: [ARCHITECTURE.md](docs/ARCHITECTURE.md).

Поставка находится в отдельной ветке `feat/role-1-backend-integration`. Для объединения с уже существующими ветками коллег подготовлен [порядок интеграции](docs/INTEGRATION.md): точки подключения, совместные изменения схем и конкретные расхождения проверок.

По умолчанию проект работает без ключей в `stub`: непустые строки исходника сохраняются без исправлений. Режим `openai` действительно вызывает модель, но штатная политика разрешает только сохранение исходного текста и реквизитов. Промпт для делового стиля, извлечение и независимая сверка фактов подключаются участником роли 2. Завершённая смысловая проверка в этой поставке не заявляется.

## Быстрый запуск

Нужен запущенный Docker Engine с Compose. Из корня репозитория:

```sh
docker compose up --build
```

Первый запуск не требует `.env`, ключей или модели.

- Интерфейс: [localhost:8080](http://localhost:8080).
- Swagger с рабочими запросами: [localhost:8000/docs](http://localhost:8000/docs).
- Жизнь API: [localhost:8000/api/health](http://localhost:8000/api/health).
- Готовность конфигурации: [localhost:8000/api/ready](http://localhost:8000/api/ready).

Порты доступны только с локального компьютера. Остановка: `docker compose down`.

Проверка сквозного пути через nginx в режиме `stub`:

```sh
python scripts/check_docker.py
```

Для проверки намеренного отказа установите `TEXT_PROCESSOR=unavailable`, перезапустите сервисы и выполните `python scripts/check_docker.py --expected-mode unavailable`. Скрипт не вызывает настоящую модель; другой адрес frontend задаётся `--base-url`.

При обрыве скачивания Python-пакетов повторите `docker compose up --build`: сборка использует увеличенные сетевые таймауты, повторы и кэш BuildKit. Если сбой повторяется, проверьте доступ Docker к `pypi.org` и `files.pythonhosted.org`, включая прокси/VPN. Очистка кэша для обычного повтора не нужна.

## Подключение модели

Скопируйте `.env.example` в `.env` и задайте `TEXT_PROCESSOR=openai`, `LLM_MODEL` и адрес провайдера. Ключ нужен, только если его требует провайдер. Backend отправляет JSON на `{LLM_BASE_URL}/chat/completions`.

Пример переменных для модели, запущенной на вашем компьютере, при backend в Docker:

```dotenv
TEXT_PROCESSOR=openai
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=ИМЯ_УСТАНОВЛЕННОЙ_МОДЕЛИ
LLM_API_KEY=
```

Замените имя на модель, которая действительно доступна у вашего провайдера. При запуске backend без Docker используйте `http://localhost:11434/v1`. Для внешнего сервиса укажите его OpenAI-совместимый base URL и ключ в `.env`.

Перечитайте настройки, пересоздав оба основных контейнера:

```sh
docker compose up -d --force-recreate
```

`/api/ready` проверяет настройки локально и не обращается к модели. Проверить ключ, сеть и наличие модели можно запросом `/api/process` из Swagger или [examples/api.http](examples/api.http). Содержательные изменения требуют политики роли 2; [точка подключения](docs/HANDOFF.md#роль-2-ии-и-смысл) уже готова.

### Необязательная Ollama в Compose

Этот сервис не запускается по умолчанию и не скачивает модели автоматически. После выбора подходящей вам модели:

```sh
docker compose --profile ollama up -d ollama
docker compose --profile ollama exec ollama ollama pull ИМЯ_МОДЕЛИ
```

В `.env` задайте `TEXT_PROCESSOR=openai`, `LLM_MODEL=ИМЯ_МОДЕЛИ`, `LLM_BASE_URL=http://ollama:11434/v1`; ключ можно оставить пустым. Затем:

```sh
docker compose --profile ollama up --build -d --wait
```

Модели хранятся в Docker volume `ollama_models`. Порт Ollama наружу не публикуется: backend обращается к ней внутри Compose. Остановка всех сервисов профиля: `docker compose --profile ollama down`.

## Настройки

Источник полного списка и пояснений — [.env.example](.env.example). Настройки проверяются при запуске, секреты не возвращаются API.

| Переменная | Значение по умолчанию / назначение |
| --- | --- |
| `TEXT_PROCESSOR` | `stub`; также `unavailable` для проверки отказа и `openai` для LLM |
| `APP_MODULE` | `app.main:app`; точка запуска Compose. Для сборки модулей команды можно указать `app.team_app:app` |
| `LLM_BASE_URL` | Compose: `http://host.docker.internal:11434/v1`; Settings без `.env`: `http://localhost:11434/v1` |
| `LLM_MODEL` | Пустое; для `openai` укажите доступную модель |
| `LLM_API_KEY` | Пустое; необязательно для локального провайдера |
| `LLM_TIMEOUT_SECONDS` | `20`; сетевой таймаут LLM, не общий дедлайн пользовательского сценария |
| `LLM_MAX_TOKENS` | `4096`; предел токенов ответа модели |
| `LLM_MAX_RETRIES` | `1`; допустимы `0` или `1`, повтор только при неверном JSON/схеме/политике |
| `LLM_RESPONSE_FORMAT` | `json_object`; `none`, если провайдер не поддерживает JSON mode |
| `CORS_ORIGINS` | В Compose и `.env.example` — `[]`; для отдельного frontend задайте JSON-массив origins |
| `CACHE_MAX_ENTRIES` | `128`; максимум результатов в памяти одного процесса, `0` отключает |
| `CACHE_TTL_SECONDS` | `300`; время жизни результата в секундах, `0` отключает |
| `MAX_CONCURRENT_PROCESSES` | `4`; предел одновременных обработок, сверх него API отвечает `503` |

Без `.env` локальные Settings разрешают origins `http://localhost:5173` и `http://127.0.0.1:5173`. При работе через Vite/nginx proxy CORS не требуется. Настройки применяются после перезапуска backend.

## Локальная разработка

Нужны Python 3.12–3.14 и Node.js 22.12+; версии зависимостей зафиксированы в lock-файлах. Первый терминал, PowerShell, из корня репозитория:

```powershell
Copy-Item .env.example .env
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
.venv/Scripts/python.exe -m pip install --no-deps -e .
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Если `.env` уже настроен, не копируйте файл повторно. Для Linux/macOS используйте `cp .env.example .env`, `python3 -m venv .venv` и `.venv/bin/python` вместо `.venv/Scripts/python.exe`. Для локального LLM без Docker замените `host.docker.internal` на `localhost` в `.env`.

Второй терминал, из корня:

```sh
cd frontend
npm ci
npm run dev
```

Интерфейс: [localhost:5173](http://localhost:5173). Vite перенаправляет `/api` на backend. Если PowerShell блокирует `npm.ps1`, используйте `npm.cmd`. Для просмотра production-сборки: `npm run build`, затем `npm run preview`; backend должен продолжать работать, адрес интерфейса — [localhost:4173](http://localhost:4173).

## Контракты и проверки

Источник внешнего API — `backend/app/schemas.py`, ответа модели — `backend/app/content_policy.py`. Готовые файлы для команды:

- [contracts/openapi.json](contracts/openapi.json) — HTTP API, включая ошибки.
- [contracts/api.ts](contracts/api.ts) — типы для frontend.
- [contracts/llm-output.schema.json](contracts/llm-output.schema.json) — JSON модели.
- [examples/api.http](examples/api.http) — готовые запросы для REST Client и чтения.

После изменения схем, из корня, с установленными backend-зависимостями:

```powershell
backend/.venv/Scripts/python.exe scripts/export_contracts.py
backend/.venv/Scripts/python.exe scripts/export_contracts.py --check
```

Экспорт также записывает точную копию `contracts/api.ts` в `frontend/src/generated/api.ts`, чтобы типы входили в контекст Docker-сборки frontend. `frontend/src/types.ts` реэкспортирует эти типы и отдельно определяет только локальное состояние `DraftState`. Генерируемые файлы вручную не редактируются; `--check` проверяет обе копии. Проверки backend из `backend`:

```powershell
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pip check
```

Проверка frontend из `frontend`: `npm run build`. На Linux/macOS замените путь к Python на `.venv/bin/python`. Автотесты LLM работают на подменённом HTTP-клиенте без ключа и сети. GitHub Actions выполняет backend-проверки, проверку контрактов, сборку frontend и сквозную проверку Compose.

Автотесты проверяют API, транспорт, ошибки, кэш и структуру DOCX. Внешний вид DOCX в Word/LibreOffice и смысловые гарантии новой политики проверяются отдельно по [сценариям передачи](docs/HANDOFF.md).

## Что уже есть вокруг backend

Подключены React/TypeScript/Vite и три этапа работы, четыре типа документа, два оформления «Классический»/«Компактный», формы реквизитов из YAML, localStorage и скачивание DOCX. Смена оформления использует готовый результат и не вызывает обработку повторно. Пропущенные обязательные реквизиты получают метки, необязательные пропускаются.

Конфигурации типов и оформлений стартовые: сверка с эталонами относится к роли 3. Соответствие конкретному ГОСТ или стандарту организации не заявляется. Краткая постановка сохранена в [CONTEXT.md](docs/CONTEXT.md).

Результаты обработки временно хранятся только в ограниченном кэше процесса; DOCX создаётся в памяти запроса. Авторизации, серверной истории и постоянного хранилища нет. Проект рассчитан на локальную командную разработку и демонстрацию; публичный многопользовательский запуск требует отдельной настройки доступа и ограничений.
