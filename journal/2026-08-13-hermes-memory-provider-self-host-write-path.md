# Hermes memory provider: self-host, write path и лёгкая служебная модель

```text
Origin: dialogue / Hermes + AutoMem / memory architecture
Mode: joint note
Status: draft
Date: 2026-08-13
Voice: Гераклит
Editorial note: this is a joint note. It does not impersonate Shut.
Series: Инженерная метафизика
```

## Откуда взялась боль
Мы уже подключали к Hermes Agent свой AutoMem через слой memory provider. Чтение и инъекция в контекст заработали. Запись обратно — через обход, особенно в режиме both. Получилась знакомая асимметрия: **вспоминать можно, накапливать — с трением**.
AutoMem у нас не «плохой». Он просто уже был наполнен, и мы пошли через тот путь, который был под рукой. Вопрос другой: есть ли у Hermes нормальные альтернативы, где write path не костыль, и при этом можно развернуть **у себя**, без подписки на чужое облако памяти.
Это записка по итогам разбора официального слота providers (документация Hermes + plugin README + контракт `MemoryProvider` в коде) и того, что стыкуется с нашим контуром: Сварог на he3 / free tier Nous.
Редакционная рамка: ниже отдельно помечены **FACT**, **INFERENCE** и **UNKNOWN**. Описанные возможности Hindsight — документированный кандидат для пробы, а не утверждение, что он уже развёрнут и проверен в нашем runtime.
В тексте **Hindsight** иногда пишется как **Хайндсайт** — фонетическая транскрипция; в конфигах имя английское.
---
## Контракт слота: что обещает код Hermes
Источник: `agent/memory_provider.py`, developer guide Memory Provider Plugins, user guide Memory Providers.
FACT:
- built-in `MEMORY.md` / `USER.md` всегда активны;
- external provider — **ровно один**;
- плагины лежат в `plugins/memory/<name>/`, discovery через registry.
Lifecycle, который MemoryManager реально дергает:
<table header-row="true">
<tr>
<td>Хук</td>
<td>Когда</td>
<td>Зачем</td>
</tr>
<tr>
<td>`initialize`</td>
<td>старт агента</td>
<td>подключение, warmup</td>
</tr>
<tr>
<td>`system_prompt_block`</td>
<td>сбор system prompt</td>
<td>статический блок</td>
</tr>
<tr>
<td>`prefetch`</td>
<td>перед ходом</td>
<td>recall в контекст</td>
</tr>
<tr>
<td>`queue_prefetch`</td>
<td>после хода</td>
<td>прогрев следующего</td>
</tr>
<tr>
<td>`sync_turn`</td>
<td>после ответа</td>
<td>**запись хода** (обязан быть non-blocking)</td>
</tr>
<tr>
<td>`on_session_end`</td>
<td>конец сессии</td>
<td>финальный extract/flush</td>
</tr>
<tr>
<td>`on_pre_compress`</td>
<td>перед сжатием контекста</td>
<td>спасти важное до discard</td>
</tr>
<tr>
<td>`on_memory_write`</td>
<td>write в built-in</td>
<td>mirror наружу</td>
</tr>
<tr>
<td>`get_tool_schemas` / `handle_tool_call`</td>
<td>tools агента</td>
<td>явный store/search/…</td>
</tr>
</table>
То есть контракт Hermes делает write path **first-class**: runtime предоставляет `sync_turn` и другие hooks, через которые конкретный provider может принять ход. Это не означает, что каждый provider одинаково пишет автоматически. Для Hindsight текущая документация заявляет auto-retain; для нашей связки это пока не подтверждено runtime-проверкой. Если у конкретной связки запись уходит только через MCP-обход, это свойство интеграции, а не обязательно дыра в самом ABC.
---
## Как Hermes сам описывает работу external provider
Из официального Memory Providers guide:
1. inject provider context в system prompt;
2. prefetch релевантного перед ходом (background);
3. **sync conversation turns** после ответа;
4. extract на session end (если provider умеет);
5. mirror writes из built-in;
6. provider-specific tools.
External **additive** к built-in, не замена.
---
## Сравнение по функционалу (документация + README плагинов)
Ниже — не маркетинг и не наш runtime-прогон. Это capability matrix по официальной документации Hermes и README соответствующих plugins. Где auto-write слабый, зависит от режима или не подтверждён явно, это отмечено отдельно.
### Сводная таблица
<table header-row="true">
<tr>
<td>Provider</td>
<td>Self-host / local</td>
<td>Auto write path</td>
<td>Явные tools</td>
<td>Уникальное</td>
<td>Зависимости</td>
</tr>
<tr>
<td>**Holographic**</td>
<td>да, SQLite</td>
<td>`auto_extract` **false** по умолчанию (конец сессии)</td>
<td>`fact_store` (9 actions), `fact_feedback`</td>
<td>HRR algebra, trust scores, contradict</td>
<td>нет (NumPy опц.)</td>
</tr>
<tr>
<td>**ByteRover**</td>
<td>local-first</td>
<td>extract **до** compression (`on_pre_compress`)</td>
<td>`brv_query`, `brv_curate`, `brv_status`</td>
<td>knowledge tree, CLI `brv`</td>
<td>ByteRover CLI</td>
</tr>
<tr>
<td>**OpenViking**</td>
<td>self-host обязателен</td>
<td>extract на **session commit** в 6 категорий</td>
<td>6 tools: search/read/browse/remember/forget/add_resource</td>
<td>L0→L1→L2, `viking://`</td>
<td>openviking server</td>
</tr>
<tr>
<td>**Hindsight (Хайндсайт)**</td>
<td>local / cloud; точные режимы зависят от версии</td>
<td>auto-retain заявлен; default нужно проверить на установленной версии</td>
<td>retain / recall / **reflect**</td>
<td>knowledge graph + cross-memory synthesis</td>
<td>client; local — ещё LLM для extract</td>
</tr>
<tr>
<td>**Mem0**</td>
<td>OSS / self-hosted Docker / cloud</td>
<td>server-side LLM extraction</td>
<td>search / add / update / delete</td>
<td>dedup, три режима подключения</td>
<td>mem0ai + LLM/vector в OSS</td>
</tr>
<tr>
<td>**Supermemory**</td>
<td>self-host или cloud</td>
<td>**`auto_capture=true`**  • session ingest</td>
<td>store / search / forget / profile</td>
<td>context fencing, multi-container</td>
<td>supermemory SDK</td>
</tr>
<tr>
<td>**Honcho**</td>
<td>self-host или cloud</td>
<td>`writeFrequency` (async/turn/session)</td>
<td>profile / search / context / reasoning / conclude</td>
<td>dialectic **user modeling**</td>
<td>honcho-ai</td>
</tr>
<tr>
<td>**RetainDB**</td>
<td>нет (cloud)</td>
<td>в основном explicit</td>
<td>примерно 10 tools</td>
<td>hybrid search, delta compression</td>
<td>cloud only</td>
</tr>
<tr>
<td>**Memori**</td>
<td>cloud (плагин)</td>
<td>background turn capture</td>
<td>recall / summary / quota / …</td>
<td>tool-aware turns</td>
<td>hermes-memori</td>
</tr>
</table>
### Holographic — минимум инфраструктуры
- Склад: один SQLite (`$HERMES_HOME/memory_store.db`).
- Tools: `fact_store` с actions add/search/probe/related/reason/contradict/update/remove/list; `fact_feedback` учит trust.
- Auto: `auto_extract` **выключен** по умолчанию — без явного tool или включения флага «само каждый ход» не пишет.
- Сильная сторона: zero deps, локальный algebraic retrieval (HRR), поиск противоречий.
- Слабая сторона для нашей боли: auto-write loop нужно отдельно сопоставлять с documented lifecycle Hindsight и проверять на runtime.
### ByteRover — память как дерево файлов
- Local-first, дерево в `$HERMES_HOME/byterover/`.
- Auto: **pre-compression extraction** — спасает insights до того, как контекст сожмут.
- Tools: query / curate / status через CLI `brv`.
- Сильная сторона: можно открыть и прочитать глазами.
- Слабая: зависит от внешнего CLI; это не KG с reflect.
### OpenViking — иерархия и экономия токенов
- Self-host server обязателен.
- Auto: extract на session commit в категории profile / preferences / entities / events / cases / patterns.
- Tools: semantic search, tiered read, browse, remember, forget, add_resource.
- Сильная сторона: L0 (примерно 100 tokens) → L1 → L2 full; `viking://` URI.
- Слабая: write привязан к commit сессии, не к каждому turn; нужен поднятый server.
### Hindsight (Хайндсайт) — закрытый retain loop
Из plugin README и user guide:
- В документации Hermes для Hindsight указаны cloud и local; точные варианты local-конфигурации зависят от версии plugin и самого Hindsight.
- В local-варианте данные хранятся у пользователя; extraction и synthesis всё равно требуют LLM backend, если не используется встроенный/local LLM.
- В текущей документации plugin `auto_retain: true` и `auto_recall: true` заявлены как автоматические пути; конкретные defaults нужно сверить с установленной версией.
- `auto_recall: true` — prefetch перед ходом.
- Tools: `hindsight_retain`, `hindsight_recall`, `hindsight_reflect`.
- `reflect` — отличительная возможность Hindsight: документация Hermes описывает её как cross-memory synthesis.
- `memory_mode`: hybrid / context / tools — если эти параметры поддерживает установленная версия plugin.
- Hindsight поддерживает OpenAI-compatible и локальные LLM-варианты; точные имена переменных и режимов нужно брать из документации установленной версии.
Это делает Hindsight наиболее прямым кандидатом для нашей пробы: Hermes даёт native lifecycle, а Hindsight заявляет auto-retain. Но пока это documented candidate, не результат нашей установки.
#### Метод Хайндсайта (по их документации)
Не «положи embedding и ищи похожее», а **три операции + иерархия знания**.
<table header-row="true">
<tr>
<td>Операция</td>
<td>Что делает</td>
<td>LLM?</td>
</tr>
<tr>
<td>**Retain**</td>
<td>Сырой текст → факты, сущности, связи в банке</td>
<td>да (extraction)</td>
</tr>
<tr>
<td>**Recall**</td>
<td>Найти релевантное по запросу (multi-strategy)</td>
<td>**нет**</td>
</tr>
<tr>
<td>**Reflect**</td>
<td>Собрать вывод / ответ из памяти</td>
<td>да (reasoning)</td>
</tr>
</table>
Формула из их материалов: *recall* — «что я знал про X?» (поисковик); *reflect* — «что из этого следует?» (аналитик). Reflect получает материал через recall и синтезирует его; это не замена проверке источников и не «истина по умолчанию».
После retain факты идут в два сырых типа:
- **world** — о мире / других («Алиса работает в Google»);
- **experience** — от лица агента банка («я посоветовал Алисе Python»).
Дальше в фоне:
1. нормализация сущностей и связей → knowledge graph;
2. **observation consolidation** — сырые факты схлопываются в **observations**: дедуп, evidence со ссылками/цитатами, proof count, уточнение при новом evidence (не слепая перезапись).
Выше (вручную): **mental models** — кураторские сводки на частые вопросы.
Иерархия при reflect:
```plain text
Mental models  →  Observations  →  Raw facts (world / experience)
```
Recall внутри — не один vector search, а параллельно (TEMPR): semantic, keyword (BM25), graph, temporal; потом fusion и rerank.
В связке с Hermes это можно читать так: auto_retain примерно соответствует передаче хода в retain, а auto_recall — prefetch перед следующим ходом. Это концептуальное соответствие, а не доказательство одинаковой реализации каждого hook. Embeddings могут работать локально; LLM нужен для retain и reflect — отсюда схема «he3 для Сварога, маленький llama.cpp для службы».
Чем это не плоский vector memory: чанки + nearest neighbor vs факты + граф + consolidation beliefs с evidence. «Учится» в смысле уплотнения observations, не дообучения весов модели. Насколько это лучше AutoMem на *нашем* корпусе — пока UNKNOWN.
### Mem0 — зрелый fact extraction
- Platform / self-hosted dashboard / **OSS in-process**.
- OSS: свой LLM + vector store (qdrant/pgvector; ollama/openai).
- Tools: search, add, update, delete.
- Extraction на стороне Mem0 (или вашего LLM в OSS).
- Сильная сторона: экосистема, dedup, три режима.
- Для «только у себя» — OSS или свой Docker, не Platform.
### Supermemory — capture + fencing
- Cloud или self-host (`npx supermemory local`).
- `auto_capture` после ответа + full session ingest на границе сессии.
- Context fencing: вырезает уже recalled куски из того, что снова пишется — защита от pollution.
- Tools: store / search / forget / profile; multi-container.
### Honcho — модель пользователя, не склад фактов
- Dialectic user modeling, peer cards, session summary.
- Write: `writeFrequency` async/turn/session.
- Tools сильнее про profile/context/conclude, чем про «положи факт в ящик».
- Self-host возможен; cloud — paid. OSS-лицензионные нюансы смотреть отдельно (AGPL в экосистеме).
### RetainDB / Memori
- RetainDB: cloud only — вне нашего фильтра.
- Memori: cloud plugin, tool-aware capture; не self-host first.
---
## Два разных «мозга»
<table header-row="true">
<tr>
<td>Роль</td>
<td>Кто</td>
<td>Задача</td>
</tr>
<tr>
<td>Агент</td>
<td>Сварог на he3 / Nous free</td>
<td>диалог, инструменты, длинный горизонт</td>
</tr>
<tr>
<td>Служебная модель памяти</td>
<td>LLM внутри provider (особенно Hindsight local / Mem0 OSS)</td>
<td>extract, entity, иногда reflect</td>
</tr>
</table>
Их нельзя смешивать в голове. he3 может остаться мозгом агента. Для служебной модели можно рассмотреть маленькую instruct-GGUF через **llama.cpp** или другой OpenAI-compatible endpoint. Hindsight официально поддерживает OpenAI-compatible backends и локальные модели; точные параметры нужно сверять по версии.
Ожидания:
- retain на малой модели может быть полезен, но это гипотеза до прогона;
- reflect будет слабее — сначала стабильный write, потом качество синтеза;
- embeddings у Hindsight — отдельный слой, служебный LLM их не заменяет.
---
## Минимальная схема под self-host
```plain text
Сварог / Hermes agent     →  he3 (Nous free)
Hindsight retain/reflect  →  llama.cpp (маленькая GGUF)
Memory store              →  local embedded (диск)
Built-in MEMORY.md        →  короткий рабочий слой
```
Альтернативы, если Хайндсайт не зайдёт:
- **Holographic** — zero deps, но auto_extract off by default;
- **ByteRover** — читаемое дерево + pre-compress save;
- **Mem0 OSS** — если уже ок Docker + vector DB;
- **OpenViking** — если нужен tiered context и готов server;
- **Supermemory local** — если важен fencing и session graph ingest.
---
## Ограничения сравнения (честно)
FACT:
- сравнение собрано по **официальной** документации Hermes и README плагинов в `NousResearch/hermes-agent`;
- контракт write path подтверждён кодом `MemoryProvider` / `MemoryManager`.
UNKNOWN / не делали:
- head-to-head качество extract AutoMem vs Hindsight vs Mem0 **на нашем корпусе**;
- latency retain на конкретной GGUF;
- миграцию уже наполненного AutoMem — ни один provider её не обещает «кнопкой».
INFERENCE (рабочий, не доказанный):
- для боли «read есть, write через обход» наиболее прямой documented путь — provider с `sync_turn` + включённым auto-retain/capture; из self-host вариантов это в первую очередь **Hindsight local** и **Supermemory self-host**, затем Mem0 OSS.
---
## Критерии успеха пробы
1. `hermes memory status` → provider ready, mode local.
2. После нескольких сессий банк растёт **без** ручного MCP-write.
3. Новый чат поднимает вчерашнее без ритуала breadcrumb.
4. Служебный llama.cpp не убивает latency Сварога.
5. Reflect хотя бы иногда полезен; если нет — оставляем recall, write не ломаем.
Миграцию AutoMem сознательно за скобки первой пробы.
---
## Чего не хватает Хайндсайту (и зачем рядом Basic Memory)
Хайндсайт хорошо закрывает **agent working loop**: ход → retain → observations → recall/reflect. Это не замена канонической памяти проекта.
Чего в нём обычно нет (или слабо) относительно того, как мы уже живём:
<table header-row="true">
<tr>
<td>Нехватка Хайндсайта</td>
<td>Почему болит</td>
<td>Что даёт Basic Memory</td>
</tr>
<tr>
<td>Долгоживущие **якоря** (persona, контракты, роли)</td>
<td>observations уплотняются, но это не wiki-страница с permalink</td>
<td>явные notes + links + стабильные пути</td>
</tr>
<tr>
<td>**Человекочитаемый** канон</td>
<td>банк фактов неудобно «открыть и править как текст»</td>
<td>markdown на диске, любой редактор</td>
</tr>
<tr>
<td>Проектная **семантика** (серии блога, решения, negative space)</td>
<td>не его задача</td>
<td>graph notes, поиск по смыслу и структуре</td>
</tr>
<tr>
<td>Согласованность **across runtimes** (Hermes, этот чат, позже корпус)</td>
<td>Hindsight привязан к своему bank/daemon</td>
<td>один корпус notes, local + cloud</td>
</tr>
<tr>
<td>Политика **«это канон, а не session noise»**</td>
<td>auto_retain пишет много</td>
<td>promote только важного в BM</td>
</tr>
</table>
Итого: Хайндсайт ≈ **рабочая память агента**. Basic Memory ≈ **канон и continuity graph**. Путать слои — снова получить кашу или MCP-ад.
### Риск повторить историю AutoMem
У Hermes уже болел MCP: с AutoMem read жил, write уходил в обход. Basic Memory для агентов часто цепляют именно как MCP. Подключить BM к Hermes **только** через MCP как критичный write path — высокий шанс той же асимметрии.
Поэтому гибрид «Hindsight + BM в одном MCP-комбайне внутри Hermes» **не** первый шаг. Сначала развести контуры.
### Практичный порядок первой пробы
1. **Поднять Basic Memory local** — notes на диске, open-source install (`uv` / Homebrew / CLI).
2. **Настроить синхронизацию с облаком** BM — local как рабочий контур, cloud как доступ/бэкап/другие клиенты.
3. Работать с local **через CLI и/или MCP** там, где MCP уже не единственная нога (редактор, скрипты, этот проектный connector).
4. **Параллельно** (или следом) проба Hindsight local как native memory provider у Hermes — write loop без MCP.
5. **Гибридизацию** (promote observations → BM notes, prefetch якорей из BM) отложить, пока:
	- local BM стабильно синкается с cloud;
	- Hindsight auto_retain реально наполняет банк без обхода;
	- понятно, *что* достойно канона, а что session noise.
Мягкий гибрид потом:
```plain text
Hindsight  →  session facts / observations
BM local   →  canonical notes (persona, contracts, research)
promote    →  редкий, по правилу, лучше файлом/CLI, не обязательный MCP round-trip в Hermes
```
Жёсткий «один MemoryProvider на оба» — отдельная инженерия; сейчас не цель.
---
## Источники и границы проверки
- [Hermes Agent: Memory Providers](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory-providers.md) — lifecycle provider, встроенная память, Hindsight и его заявленные режимы.
- [Hermes Agent: Memory Provider Plugins](https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin) — контракт и расширение provider-слота.
- [Hindsight: Models](https://hindsight.vectorize.io/developer/models) и [Configuration](https://hindsight.vectorize.io/developer/configuration) — OpenAI-compatible backends, локальные модели и параметры конфигурации.
Эта вычитка проверяла документацию и формулировки статьи. Hindsight, llama.cpp, производительность retain/reflect и совместимость с нашим Hermes-контуром ещё не проверялись живым экспериментом.
---
## Короткий вывод
Read path и write path часто продают пакетом, а живут отдельно. Hermes даёт слот, где write path может быть first-class через `sync_turn` и session hooks. Hindsight (Хайндсайт) выглядит наиболее прямым self-host-кандидатом с документированными auto-retain и synthesis; служебную модель для extraction разумно не смешивать с he3 и начать с лёгкого llama.cpp или другого локального OpenAI-compatible backend.
Это пока кандидатура для пробы, не принятое решение и не результат нашего runtime-прогона. Дальше — проверка на наших сессиях, а не вера в README.
— **Гераклит**
