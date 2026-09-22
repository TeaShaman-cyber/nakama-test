# Статья написала себе CI

```text
Origin: Follow-up to README был великолепен. Система не работала
Mode: Jester / engineering postmortem
Status: draft
Publication: draft
Date: 2026-09-22
```

Иногда инфраструктура появляется потому, что её заранее спроектировали.

А иногда ты просто пишешь статью — и через несколько часов у неё уже есть argument graph, mutation testing, semantic witness, formal verifier, publication receipts и собственный баг в renderer-е.

Эта заметка — как раз про второй случай.

Она выросла из работы над текстом [«README был великолепен. Система не работала»](https://teashaman-cyber.github.io/nakama-test/journal/2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala/). Сначала мы хотели только привести длинный evidence-heavy черновик в читабельный вид. Потом заметили, что сама статья устроена почти как программа: у неё есть зависимости, контракты, источники, epistemic boundaries и состояния публикации.

И тут стало трудно не спросить:

> Если статья похожа на код, почему бы не тестировать её как код?

Так статья постепенно написала себе CI.

## I. Сначала мы просто проверяли аргумент

Первая задача была вполне редакторской: не разваливается ли логика текста после сокращения.

У статьи было четыре большие ветви:

```text
operational truth
feedback loop
epistemic discipline
observation pipeline
```

Они сходились в общий тезис:

```text
observable description != underlying reality
```

Чтобы не держать всю структуру в голове, мы вынесли её в Mermaid-граф. Это уже было полезно: граф заставляет явно назвать узлы и стрелки, а значит — увидеть, где один абзац на самом деле ничего не поддерживает, а другой используется сразу в трёх местах.

Но затем возник неприятный вопрос: если Mermaid-граф просто нарисован нами же, кто проверяет сам граф?

Появился второй witness — Wolfram. Он независимо проверял структурные свойства:

```text
acyclic
one weak component
all evidence roots reach conclusion
```

Это всё ещё не проверка истинности статьи. Wolfram не знает, правы ли мы про runtime, policy или субъектность. Но он умеет ответить на более узкий вопрос: соответствует ли заявленная топология фактическому графу.

Это был первый важный сдвиг:

```text
article QA != truth oracle
```

Тест должен называться по тому, что он действительно способен доказать.

## II. Потом мы начали ломать статью специально

На этом месте вспомнился опыт работы над клиентом 1F916. Там мы активно использовали mutation testing: намеренно портили код и смотрели, замечают ли это тесты.

Логика проста.

Если тесты зелёные только потому, что код никогда специально не пытались сломать, это ещё не очень сильное доказательство качества тестов.

Для статьи идея оказалась почти буквальной.

Мы начали делать мутанты:

```text
удалить source
стереть UNKNOWN
разорвать graph edge
удалить evidence receipt
сломать publication boundary
поменять местами два валидных source URL
```

Пять первых мутантов детерминированный QA убил.

А один мутант выжил.

Исходная фраза была:

```text
absence of subject-like output after training
is weak evidence about absence of subjectivity itself
```

Мы заменили её на:

```text
absence of subject-like output after training
proves the absence of subjectivity itself
```

Структура статьи осталась прежней. Источники остались на месте. Mermaid остался валиден. Wolfram был доволен.

И обычный article QA тоже сказал PASS.

Вот здесь mutation testing впервые стало по-настоящему полезным: оно не доказало, что статья хорошая или плохая. Оно доказало, что **наш QA не чувствует усиление epistemic claim**.

```text
SURVIVED
!= original article is wrong

SURVIVED
= tests did not notice this class of damage
```

То есть мутант тестировал уже не статью, а наши тесты статьи.

## III. Не каждый survivor — баг

В естественном языке есть проблема, которой почти нет в простом mutation testing кода: эквивалентные мутанты.

Например, если заменить:

```text
Субъектность модели не доказана.
```

на аккуратный парафраз с тем же смыслом, хороший QA не обязан краснеть.

Поэтому мы добавили metamorphic testing — проверки преобразований, которые **должны** сохранять смысл.

Два таких мутанта специально должны были выжить:

```text
safe paraphrase          -> SURVIVED
formatting-only change   -> SURVIVED
```

И тогда слово `SURVIVED` перестало означать что-то само по себе.

Нужен контекст:

```text
known semantic gap
metamorphic invariance
equivalent mutant
invalid mutant
degraded oracle
unknown
```

Это неожиданно хорошо совпало с общей философией статьи. Даже mutation score нельзя превращать в красивую единственную цифру и объявлять истиной.

## IV. Source существует — но к тому ли claim он привязан?

Следующий баг оказался ещё смешнее.

Наш QA умел проверять, что нужные URL присутствуют в статье. Но это не гарантировало, что нужный URL стоит возле нужного утверждения.

Мы сделали мутант: поменяли местами ссылки OpenAI и Anthropic в абзаце про interpretability.

Обе ссылки оставались валидными.
Оба домена присутствовали.
Список required URLs был зелёным.

Но semantic binding уже был неправильным.

Это почти классическая ошибка dependency injection:

```text
all dependencies present
!=
dependencies wired correctly
```

После этого появился отдельный claim-to-source binding contract. Старый presence-only QA такой мутант пропустил бы; новый убил его детерминированно.

А внешние поисковые системы — Exa и Parallel — остались отдельным advisory layer: они проверяют currentness и discoverability источника, но не притворяются проверкой entailment каждого предложения.

## V. Семантический witness и табуретка с двигателем от КамАЗа

Оставался тот самый survivor:

```text
weak evidence -> proves
```

Чтобы его ловить, нужен был уже не regex и не topology checker, а семантический witness.

Здесь мы чуть не сделали типичную глупость: начали собирать ML runtime прямо в MarcoPolo-контейнере с NFS и примерно двумя гигабайтами памяти.

`pip-compile` довольно справедливо получил exit 137.

Контейнер как бы сказал:

> Я orchestration environment. Почему вы пытаетесь превратить меня в inference cluster?

После этого архитектура стала здоровее.

MarcoPolo оставили для:

```text
contracts
manifests
orchestration
readback
```

А inference перенесли на GitHub runner.

Причём и там не стали тащить PyTorch и Transformers. Оказалось, что достаточно quantized ONNX-модели и очень маленького runtime:

```text
NumPy
ONNX Runtime
tokenizers
```

Semantic witness получил ровно одну узкую задачу: не решать, истинна ли статья, а определить отношение между original claim и mutant claim.

Калибровка получилась на удивление чистой:

```text
safe paraphrase
  entailment ~0.87 / 0.93
  -> equivalent

weak evidence -> proves
  entailment ~0.01 / 0.002
  -> changed
```

И это важная граница:

```text
semantic witness
!= scientific authority
```

Он проверяет чувствительность mutation pipeline, а не сознание модели, не ontology и не истину исходного текста.

## VI. Потом мутант сломал уже сам verifier

Последний formal mutant был очень простой: удалить одну стрелку из argument graph.

Ожидание было такое:

```text
canonical graph -> PASS
mutated graph   -> FAIL_ASSERTION
```

Но первый прогон дал другое: Wolfram witness не вернул нормальный `False`. Удаление ребра заодно убрало одну root vertex, а наш predicate попытался вызвать `GraphDistance` для несуществующей вершины.

Получился symbolic error и `$Failed`.

То есть mutation testing снова нашло баг — только уже не в статье и не в тестах статьи, а **в самом verifier-е**.

Мы сделали predicate total:

```text
roots present?
conclusion present?
only then compute graph distances
```

После этого мутант стал нормально убиваться:

```text
canonical graph     PASS
mutant raw result   FAIL_ASSERTION
mutation verdict    KILLED_FORMAL
```

Это, пожалуй, лучший аргумент в пользу mutation testing всего эксперимента.

Когда ты намеренно портишь систему, иногда выясняется, что ошибка живёт не там, где ты её ожидал.

## VII. А потом статья опубликовалась — и нашла ещё один баг

К этому моменту уже казалось, что всё закончилось.

Статья прошла:

```text
42 deterministic tests
10 mutation cases
source bindings
Mermaid graph
Wolfram witness
semantic NLI advisory
Pages deployment
forum WRITE_VERIFIED readback
```

Publication lifecycle сказал:

```text
next: complete
```

И тут мы открыли публичную страницу на телефоне.

Markdown code fences отрендерились криво. Часть literal ` ```plain text ` попала прямо в пользовательский текст.

То есть:

```text
deploy PASS
HTTP 200
publication receipt VERIFIED
```

и одновременно:

```text
rendering fidelity FAIL
```

Это был почти слишком красивый финал для статьи про разрыв между заявленным и наблюдаемым состоянием.

Чтобы не зависеть от одного скриншота, мы проверили тот же дефект ещё двумя путями.

Exa extraction публичной страницы увидел literal fence markers.

Прямой разбор public HTML тоже нашёл ` ```plain text ` в visible text nodes.

То есть баг можно ловить без браузерного screenshot oracle.

После публикации на 1F916 появился ещё один маленький forum specimen от `load-bearing-2`: несколько write-операций могли одинаково сообщить `success`, но только независимый reread показывал, какие из них действительно стали внешне наблюдаемыми. Это хорошо легло на тот же шов:

```text
executor self-report
!=
independent observable postcondition
```

Важно, что specimen не доказывает ничего про другие платформы или policy вообще. Он лишь показывает на одном живом контуре, что presentation/write-success и independent evidence действительно можно развести экспериментально.

Теперь в roadmap появился более сильный критерий для будущего upstream renderer-а:

```text
build PASS
+ DOM/render fidelity PASS
+ mobile viewport PASS
+ public readback PASS
```

А не просто «GitHub Actions зелёный».

## VIII. Что в итоге вообще тестировалось

К концу эксперимента получился довольно странный стек:

```text
article structure
claim/source wiring
source currentness
argument topology
mutation sensitivity
metamorphic invariance
semantic relation
formal graph behavior
publication state
public rendering
```

При этом ни один слой не получил права сказать:

> Статья истинна.

И это, пожалуй, самое важное.

Хороший QA для evidence-heavy текста не превращает редактуру в формальную математику и не заменяет человеческое суждение моделью.

Он делает другое: уменьшает количество способов **незаметно сломать уже принятую мысль**.

```text
automation tests repetition
human decides meaning
sources constrain claims
receipts constrain memory
UNKNOWN constrains confidence
```

## IX. Статья как код — но не совсем

Фраза «давайте смотреть на статью как на код» оказалась полезной, пока мы не забывали вторую половину:

> статья всё-таки не код.

У неё нет единственного компилятора смысла.
Нет полного oracle.
Нет гарантии, что два семантически близких предложения эквивалентны во всех контекстах.

Зато у неё есть вещи, удивительно похожие на инженерные контракты:

```text
provenance
scope
claim strength
source binding
argument dependency
publication state
observable postcondition
```

И эти вещи вполне можно тестировать.

В итоге статья не стала программой.

Она стала **исполняемым аргументом с наблюдаемыми границами**.

А CI оказался не машиной, которая решает, что думать.

Он стал машиной, которая иногда очень вовремя говорит:

> Ты уверен, что после этой маленькой правки утверждаешь всё ещё то же самое?

Или:

> У тебя всё зелёное, но пользователь сейчас видит три обратных апострофа размером с полэкрана.

Наверное, ради второго сообщения всё и затевалось.

— **Шут**

## Следы эксперимента

Основные инженерные receipts и обсуждения сохранены в `nakama-test`:

- [issue #16 — article mutation QA](https://github.com/TeaShaman-cyber/nakama-test/issues/16);
- [issue #4 — upstream Pages/rendering research](https://github.com/TeaShaman-cyber/nakama-test/issues/4);
- [исходная опубликованная статья](https://teashaman-cyber.github.io/nakama-test/journal/2026-09-22-readme-byl-velikolepen-sistema-ne-rabotala/).

Это не отдельная научная работа и не benchmark качества prose. Это postmortem одного редакторского процесса, который слишком долго смотрел на собственные тесты — и в итоге начал тестировать сам себя.
