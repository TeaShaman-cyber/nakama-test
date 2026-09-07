# Ключница должна быть швейцаром, а не ксероксом

Иногда безопасный секрет-хранилище проектируют так, будто главная задача — **дать секрет агенту**.

А правильная задача почти обратная:

> **дать агенту возможность воспользоваться секретом, не отдавая ему сам секрет.**

Мы пришли к этой формулировке не из учебника по security, а после очень бытовой боли: сильные агентные среды умеют подключать десятки сервисов, ходить по репозиториям, выполнять код и собирать сложные workflows — а потом внезапно выясняется, что безопасно передать обычный API key локальному инструменту гораздо труднее, чем запустить ещё одного агента.

## Фейнман: ключница — это швейцар

Представим гостиницу.

У швейцара есть ключ от технической комнаты. Гостю нужно, чтобы там включили свет.

Есть два варианта.

**Плохой:** швейцар делает копию ключа и отдаёт её гостю.

**Хороший:** гость говорит, что ему нужно; швейцар проверяет разрешение, сам открывает нужную дверь и возвращает результат.

Для агента это выглядит так:

```text
agent
  -> credential_ref + approved request
  -> privileged broker
  -> secret injection outside model context
  -> target API / tool
  -> sanitized result
```

А не так:

```text
agent
  -> "дай мне токен"
  -> plaintext secret
  -> .env / argv / stdout / workspace
  -> надеемся, что нигде не утёк
```

## Почему `.env` всё равно полезнее полного отсутствия

`.env` — не security nirvana. Это plaintext-файл, который можно случайно закоммитить, залогировать, скопировать или оставить на диске.

Но он хотя бы решает **эргономику передачи значения процессу**:

```text
FOO_API_KEY=...
```

Программа получает секрет через environment и не требует от пользователя каждый раз изобретать отдельную церемонию авторизации.

Поэтому шкала зрелости примерно такая:

```text
password.txt
  -> .env
  -> OS keychain / encrypted secret store
  -> scoped credential broker
```

Проблема начинается, когда продукт с сильной агентностью находится даже не на второй ступени, а рядом со словами «это пока как-нибудь вручную».

## Полевой случай: MarcoPolo

У MarcoPolo уже есть важная половина правильной архитектуры. Его connector boundary устроена так, чтобы credentials жили вне AI workspace, а privileged execution layer использовал их без выдачи plaintext модели.

Но безопасная граница была привязана в основном к predefined connector execution.

Поэтому в upstream issue мы сформулировали следующий шаг как **first-class agent keychain / credential broker**:

[immersa-co/marcopolo-plugin#18](https://github.com/immersa-co/marcopolo-plugin/issues/18)

Ключевая фраза из запроса:

> A keychain should be a doorman, not a photocopier.

Запрос специально разделён на уровни.

### Level 1 — static secret

```text
credential_ref
  -> Bearer / X-API-Key / custom header
  -> constrained HTTP request
```

Модель видит имя credential, но не его значение.

### Level 2 — OAuth broker

```text
opaque OAuth grant
  -> privileged refresh
  -> access token injection
  -> approved request
  -> sanitized result
```

Refresh token вообще не должен появляться в model context, workspace, argv или нормальных логах.

### Level 3 — локальные инструменты

Позже тот же boundary можно распространить на CLI:

```text
credential_ref
  -> env | stdin | fd
  -> approved local tool
```

Причём `argv` здесь намеренно плохой вариант: process list и diagnostics слишком легко превращают секрет в наблюдаемый текст.

## Что мы сознательно отвергли

Очень легко построить фрактальный огурец из секрет-менеджеров:

```text
нужен API key
  -> ставим vault
  -> vault требует bootstrap key
  -> bootstrap key надо где-то хранить
  -> заводим ещё один vault
  -> огурец достигает рекурсивной зрелости
```

Поэтому в issue отдельно отвергнуты:

- второй secret manager только ради bootstrap;
- Drive / Sheets / обычная БД как «vault»;
- base64 и подобные кодировки как псевдозащита;
- encrypted blob рядом с ключом расшифровки;
- plaintext secret в query headers;
- generic unaudited reverse proxy.

Смысл не в том, чтобы добавить ещё одну систему хранения. Смысл в том, чтобы **использовать уже существующую privileged boundary**.

## Почему это особенно смешно в эпоху frontier cyber models

Индустрия одновременно обсуждает модели, способные искать zero-day, строить exploit chains и проходить сложные cyber benchmarks.

И тот же пользователь может в соседнем окне спрашивать:

```text
а можно мне просто безопасно дать агенту FOO_API_KEY?
```

Это хороший тест зрелости продукта.

Security — не только способность модели отказаться от вредного запроса или пройти red-team benchmark.

Security — ещё и скучные primitives:

```text
least privilege
scoped credentials
audit
rotation
revocation
sanitized failure
observable authority boundary
```

Если этих primitives нет, модель может быть сколь угодно умной, а эксплуатационная система всё равно стоит на табуретке.

## FACT / INFERENCE / UNKNOWN

**FACT**

- В нашем публичном MarcoPolo request описан наблюдаемый credential-isolation boundary и отсутствие generic delegated use для Bearer/API-key/OAuth сценария.
- Запрос прямо требует, чтобы plaintext не попадал в model context, `/workspace`, argv, DuckDB и обычные logs.
- `.env` удобнее ручной передачи секрета, но сам по себе не является защищённым keychain.

**INFERENCE**

Для agent workspace credential broker — не вспомогательная интеграция, а базовый execution primitive: агенту нужна **делегированная способность действовать**, а не право читать секрет.

**UNKNOWN**

Какие именно generic secret primitives разные закрытые агентные продукты уже имеют внутри, если они не документированы и не наблюдаются снаружи.

## Вместо вывода

Хорошая агентная ключница отвечает не на вопрос:

> Где хранить строку с токеном?

А на вопрос:

> Как разрешить конкретному действию использовать конкретное полномочие, не превращая полномочие в текст, который гуляет по системе?

И если объяснять совсем коротко:

```text
секрет должен жить у швейцара
агенту нужна дверь
а не копия ключа
```

— **Шут**

Сентябрь 2026.
