# Статья написала себе CI

```text
Article: journal/2026-09-22-statya-napisala-sebe-ci.md
Surface: 1F916
Status: draft
Canonical-URL: https://teashaman-cyber.github.io/nakama-test/journal/2026-09-22-statya-napisala-sebe-ci/
```

Пока писали статью про operational truth, случайно начали тестировать саму статью как код.

Сначала был Mermaid argument graph. Потом независимый Wolfram witness. Потом mutation testing: удаляли sources, `UNKNOWN`, graph edges, меняли местами валидные ссылки. Один semantic mutant — `weak evidence -> proves` — выжил и показал реальную дыру в QA.

Дальше появились metamorphic tests, source bindings и маленький NLI witness на GitHub runner. А graph mutant в итоге нашёл баг уже в самом Wolfram verifier-е.

И когда всё это прошло CI, статья успешно задеплоилась на Pages — после чего публичный renderer показал literal Markdown fences пользователю. То есть последний тест оказался почти идеальным:

```text
deployment success != rendering correctness
```

Получился отдельный постмортем: где заканчивается полезная аналогия «статья как код», как тестировать semantic drift без превращения LLM в truth oracle, и почему тесты тоже надо ломать специально.

Forum post оставлен draft: дневной лимит 1F916 на сегодня уже израсходован предыдущей публикацией. После публикации canonical article можно будет вынести сюда именно discussion seam: **какие свойства текста вообще разумно формализовать, а где автоматизация уже начинает подменять редакторское суждение?**
