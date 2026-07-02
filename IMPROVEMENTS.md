# Предложения по улучшению — DeckPiP

_Сгенерировано автоматически: 200 идей, из них отобрано 36 лучших._

## О проекте

DeckPiP — Decky-плагин для Steam Deck, который выводит произвольное Linux GUI-приложение
(Discord, Telegram, IDE, web-страницу) поверх запущенной игры в Gaming Mode. Обход отсутствия
overlay-API в Gamescope сделан так: Python-бэкенд (`main.py` + пакет `deckpip/`, работает под
`_root`) поднимает `Xvnc :42` + гостевое приложение + `websockify`, а фронтенд на React/TSX
(`src/`, сборка через `@decky/rollup`) рендерит `<iframe>` с noVNC-клиентом в кастомном маршруте
Steam UI. Ключевые модули бэкенда: `session.py` (жизненный цикл процессов), `vendoring.py` /
`ludusavi.py` / `cloud_sync.py` (self-contained загрузка бинарей), `mirror.py` (GameMirror через
gstreamer), `mpris.py` / `notifications.py` / `audio.py` / `ptt.py` / `trackpad.py` (интеграции
через `dbus-send`/`pactl`/`xdotool`). Фронтенд: `panel.tsx` (Quick Access UI, 1323 строки),
`pip-view.tsx` (overlay), `store-core.ts` (состояние), `api.ts` (RPC-обёртки). Тесты: pytest для
бэкенда, vitest для фронтенда; CI — `.github/workflows/build.yml`.

---

## Топ 36: приоритетные улучшения

### 1. `run_update` всегда падает: `setup.sh` требует пользователя `deck`, а бэкенд работает под root
**Категория:** Bugs / correctness · **Impact:** High · **Effort:** M
**Обоснование:** `deckpip/updater.py::run_setup` запускает `bash setup.sh` из root-процесса Decky (`_root`),
но `setup.sh:27` содержит `[[ "$(id -un)" == "deck" ]] || die "Run as the 'deck' user"`. Значит кнопка
«Run update» в System-панели гарантированно завершается с ошибкой на реальном устройстве. Нужно либо
запускать setup через `runuser -u deck`, либо вынести общую часть в скрипт, не требующий deck-пользователя.

### 2. Гостевое приложение стартует без `deck_env()` — ломается PulseAudio/DBus/Flatpak под root
**Категория:** Bugs / correctness · **Impact:** High · **Effort:** M
**Обоснование:** В `deckpip/session.py::start` guest запускается с `env = {**os.environ, "DISPLAY": DISPLAY}`,
без `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` deck-пользователя, которые как раз готовит `deck_env()`.
Под `_root` это означает, что Flatpak-Discord обращается к `/run/user/0`, а не `/run/user/1000`, и не видит
звук/сессионную шину. Guest должен запускаться с `deck_env()`, как это уже делают `audio.py`/`ptt.py`/`notifications.py`.

### 3. Файл `vncpasswd` пишется root'ом с правами 0600 — `Xvnc` под `deck` не может его прочитать
**Категория:** Bugs / correctness · **Impact:** High · **Effort:** M
**Обоснование:** `session.py::_write_vnc_passwd` вызывает `vncpasswd` как root и делает `path.chmod(0o600)`,
после чего `Xvnc` запускается через `runuser -u deck` с `-PasswordFile`. Root-owned файл с 0600 не читается
deck-пользователем → `Xvnc` не стартует с VncAuth. Нужно `chown` на deck (или права 0640/0644, т.к. loopback)
либо генерировать пароль из-под deck.

### 4. MPRIS не работает под root: `mpris.py` не использует `_as_user_argv`/`deck_env`
**Категория:** Bugs / correctness · **Impact:** High · **Effort:** S
**Обоснование:** `deckpip/mpris.py::_dbus_send` задаёт только `DISPLAY`, но не оборачивает `dbus-send` в
`runuser` и не выставляет `DBUS_SESSION_BUS_ADDRESS`. Под `_root` `dbus-send --session` попадёт на шину root'а,
где плееров нет, поэтому `list_players()` всегда пуст. Привести к тому же паттерну, что и `notifications.py`.

### 5. GameMirror ищет PipeWire-узел не в той сессии: `pw-cli`/gstreamer без deck-окружения
**Категория:** Bugs / correctness · **Impact:** High · **Effort:** M
**Обоснование:** `deckpip/mirror.py::find_gamescope_pw_node` вызывает `pw-cli ls Node` без `_as_user_argv`/`deck_env`,
а `_spawn_pipeline` запускает gstreamer с `env` без `XDG_RUNTIME_DIR`. Под root PipeWire-сокет deck-пользователя
недоступен, узел gamescope не находится → `no_gamescope_pw_node`. Обе точки должны использовать `deck_env()` и
`runuser`.

### 6. `install_websockify(force=True)` оставляет неработающий wrapper
**Категория:** Bugs / correctness · **Impact:** Med · **Effort:** S
**Обоснование:** В `deckpip/vendoring.py::install_websockify` при переустановке pip заново создаёт `bin/websockify`
(настоящий скрипт), но `.real` уже существует, поэтому ветка `if not wrapper.exists()` пропускается и PYTHONPATH-обёртка
не переустанавливается — импорт `websockify` затем падает. Нужно удалять/пересоздавать `.real` при `force=True`.

### 7. Экспорт настроек утекает GitHub PAT в открытом виде
**Категория:** Security · **Impact:** High · **Effort:** S
**Обоснование:** `main.py::export_settings` возвращает целиком `SettingsStore._load()`, включая ключ `github_token`,
а `panel.tsx::onExport` копирует это в буфер обмена и показывает в `<pre>`. Токен нужно исключать/маскировать при
экспорте (и хранить отдельно от общих настроек).

### 8. Нет проверки контрольных сумм скачиваемых бинарей (noVNC, ludusavi, rclone, websockify)
**Категория:** Security · **Impact:** High · **Effort:** M
**Обоснование:** `vendoring.py`, `ludusavi.py`, `cloud_sync.py` качают релизы с GitHub и распаковывают под
root в `DECKY_PLUGIN_RUNTIME_DIR`, полагаясь только на HTTPS. Скомпрометированный релиз/зеркало исполнится с
правами root. Нужно закрепить SHA256 рядом с пином версии и проверять его после загрузки; для websockify —
`pip install --require-hashes`.

### 9. `panel.tsx` — монолит на 1323 строки с ~40 `useState` в одном компоненте
**Категория:** Architecture / refactor · **Impact:** High · **Effort:** L
**Обоснование:** `Content()` в `src/panel.tsx` содержит все четыре вкладки (Apps/Sync/Web/System), десятки
хендлеров и состояний. Разбить на компоненты-вкладки (`AppsTab`, `SyncTab`, `WebTab`, `SystemTab`) и вынести
логику в хуки — резко снизит связность и упростит тестирование.

### 10. `NotificationMirror.stop()` может оставлять зомби `dbus-monitor`
**Категория:** Bugs / correctness · **Impact:** Med · **Effort:** S
**Обоснование:** `notifications.py::start` запускает `runuser … dbus-monitor` без `preexec_fn=os.setsid`, а
`stop()` шлёт `self._proc.terminate()` только процессу `runuser`. Дочерний `dbus-monitor` может пережить сигнал.
Использовать `os.setsid` + `killpg`, как в `session.terminate()`.

### 11. Опечатка-стиль в `src/api.ts`: два `export` на одной строке
**Категория:** Bugs / correctness · **Impact:** Low · **Effort:** S
**Обоснование:** `src/api.ts:31` — `...("settings_set");export const addCustomApp = ...` склеены в одну строку.
Работает, но это явный след ручной правки; надо разнести и добавить lint фронтенда (см. п. 12), чтобы такое ловилось.

### 12. Нет линтера/форматтера для фронтенда (eslint + prettier), CI его не проверяет
**Категория:** Tests & CI · **Impact:** Med · **Effort:** M
**Обоснование:** `package.json` имеет только `build`/`watch`/`test`/`typecheck`; `.editorconfig` задаёт стиль,
но ничем не форсится. Добавить eslint + prettier и шаг `pnpm run lint` в `build.yml` (job `frontend`) — поймало бы
дефект из п. 11 и стабилизировало стиль в 8 tsx/ts-файлах.

### 13. Жёстко зашитые `DISPLAY :42`, geometry `1280x800`, порты 5942/6901
**Категория:** Config / build · **Impact:** Med · **Effort:** M
**Обоснование:** Константы в `session.py` (`DISPLAY`, `GEOMETRY`, `VNC_RFB_PORT`, `VNC_WEB_PORT`) не настраиваются;
TROUBLESHOOTING сам признаёт проблему конфликта порта/stale-lock. Вынести в настройки + автоподбор свободного
дисплея/порта устранит целый класс «Xvnc did not start listening on 5942».

### 14. `settingsSet` вызывается на каждый keystroke (remote/path/hotkey) — нет дебаунса
**Категория:** Performance · **Impact:** Med · **Effort:** S
**Обоснование:** В `panel.tsx` поля `cloud_remote`, `cloud_path`, а также hotkey-поля через `store.set(...)`
пишут в бэкенд на каждый символ (read-modify-write JSON в `SettingsStore`). Дебаунс/`onBlur`-сохранение снизит
IO и риск потери апдейтов (см. п. 15).

### 15. `SettingsStore` не защищён от гонок read-modify-write
**Категория:** Bugs / correctness · **Impact:** Med · **Effort:** M
**Обоснование:** `settings.py::set` делает `_load()`→mutate→`_save()` без блокировки. Атомарный `os.replace`
спасает от порчи файла, но параллельные `settings_set` из разных хендлеров теряют апдейты (last-writer-wins).
Ввести `asyncio.Lock` вокруг чтения-записи или единый writer.

### 16. `diagnostics._which` не убивает зависший процесс по таймауту и содержит избыточный `except`
**Категория:** Error handling & logging · **Impact:** Med · **Effort:** S
**Обоснование:** В `deckpip/diagnostics.py` при таймауте `--version` процесс не `kill()`-ается (утечка зомби),
а `except (TimeoutError, Exception)` избыточен (TimeoutError — подкласс Exception) и глотает всё молча. Добавить
`proc.kill()` в ветке таймаута и сузить перехват.

### 17. README противоречит сам себе: «repository is public» vs «Repository is private»
**Категория:** Documentation · **Impact:** Med · **Effort:** S
**Обоснование:** `README.md:63` утверждает, что репозиторий public, а «Known gaps» (`README.md:164`) — что private
и anonymous install не работает. Одно из утверждений устарело; читатель не понимает, работает ли путь A установки.

### 18. Документация ссылается на KasmVNC/Xvfb, хотя реализация на TigerVNC `Xvnc`
**Категория:** Documentation · **Impact:** Med · **Effort:** S
**Обоснование:** `README.md` («How it works»), `docs/RESEARCH.md` и `docs/DISCORD_STREAMING.md` упоминают
`Xvfb`/KasmVNC, а `ARCHITECTURE.md` в «Security» пишет «KasmVNC bound to 127.0.0.1». Фактически используется
`Xvnc` (TigerVNC). Привести доки в соответствие с кодом (`session.py`).

### 19. `ARCHITECTURE.md` перечисляет устаревший набор pacman-зависимостей
**Категория:** Documentation · **Impact:** Med · **Effort:** S
**Обоснование:** Раздел «Runtime dependencies» упоминает `python-websockify`, `novnc`, `xterm`, `wmctrl` как
pacman-пакеты, но `defaults/install.sh` теперь вендорит websockify/novnc и убрал `xterm`/`xdotool` из required.
Синхронизировать список (иначе пользователь ставит лишнее).

### 20. `check_release`/updater ссылаются на «feature branch», а CI триггерится на `main`
**Категория:** Documentation · **Impact:** Low · **Effort:** S
**Обоснование:** `README.md:74` и тело релиза в `build.yml` говорят «push to the feature branch», хотя
`.github/workflows/build.yml` слушает `branches: [main]`. Мелкая, но вводящая в заблуждение рассинхронизация
после мержа в main.

### 21. Нет тестов на `diagnostics.py` и `ptt.py`
**Категория:** Tests & CI · **Impact:** Med · **Effort:** S
**Обоснование:** В `tests/` есть покрытие почти всех модулей, но нет `test_diagnostics.py` и `test_ptt.py`.
`ptt._set_mute` — критичная для безопасности логика (микрофон), её поведение press/release/key стоит закрепить
тестом (mock `pactl`).

### 22. GitHub Actions не запинены по SHA, `permissions: contents: write` на весь workflow
**Категория:** Security · **Impact:** Med · **Effort:** S
**Обоснование:** `build.yml` использует `actions/*@v4`, `softprops/action-gh-release@v2` по плавающим тегам и
даёт `contents: write` обоим job'ам. Запинить экшены по commit-SHA и сузить `permissions` до job'а, который
публикует релиз (supply-chain hardening).

### 23. `iframe` для Web-PiP: `allow-scripts` + `allow-same-origin` на произвольном URL
**Категория:** Security · **Impact:** Med · **Effort:** S
**Обоснование:** В `pip-view.tsx` sandbox iframe включает `allow-scripts allow-same-origin` и для noVNC, и для
произвольных пользовательских URL (bookmarks). Для web-режима это ослабляет изоляцию недоверенной страницы.
Разделить политику sandbox: минимальные права для внешних URL, полные — только для loopback-noVNC.

### 24. `PointerCapture` начинается с `top: 28` независимо от touch-mode (header 50px)
**Категория:** Bugs / correctness · **Impact:** Med · **Effort:** S
**Обоснование:** В `pip-view.tsx` overlay-слой захвата указателя жёстко `top: 28`, а высота header в touch-режиме
`HEADER_TOUCH = 50`. Возникает мёртвая зона 28–50px, где события идут в header, а не в guest, и наоборот. Привязать
`top` к `headerH`.

### 25. Нет верификации версий в едином источнике; `package.json` навсегда `0.0.1`, `plugin.json` без версии
**Категория:** Config / build · **Impact:** Med · **Effort:** M
**Обоснование:** `package.json:version` = `0.0.1`, `plugin.json` вообще без поля версии, релиз всегда `dev`.
Пользователь и `check_update` не могут отличить сборки. Ввести единый version-источник и прокидывать его в
`plugin.json`/релиз-тег.

### 26. `install_dependencies` и `run_setup` дублируют логику запуска subprocess с таймаутом
**Категория:** Architecture / refactor · **Impact:** Low · **Effort:** S
**Обоснование:** `main.py::install_dependencies` и `updater.py::run_setup` (и частично `cloud_sync._run`,
`ludusavi._run`) повторяют один паттерн `create_subprocess_exec`+`wait_for`+обрезка stdout/stderr. Вынести
общий `run_capture(argv, timeout)` — единая обработка таймаута/kill (см. также п. 16).

### 27. Молчаливое `catch(() => {})` по всему фронтенду скрывает ошибки RPC
**Категория:** Error handling & logging · **Impact:** Med · **Effort:** M
**Обоснование:** `index.tsx`, `panel.tsx`, `pip-view.tsx` изобилуют `.catch(() => {})`/`catch {}`. При проблемах
(например, PTT/mouse RPC постоянно падают) пользователь не получает сигнала, а разработчик — логов. Ввести
`logError()`-хелпер, который хотя бы пишет в консоль Decky.

### 28. `terminate()` не работает для процессов, запущенных не в своей группе (`runuser` без setsid у helper'ов)
**Категория:** Bugs / correctness · **Impact:** Med · **Effort:** M
**Обоснование:** `session.terminate`/`_signal_all` рассчитывают на `os.setsid` (есть у Xvnc/guest/websockify/mirror).
Но helper-процессы вроде notification-mirror и потенциальные будущие фоновые процессы запускаются без setsid, и
`killpg` по их pgid убьёт не то. Единый спавнер с setsid устранит риск (связано с п. 10).

### 29. Нет CI-проверки, что `pnpm-lock.yaml` соответствует `package.json` кроме `--frozen-lockfile`
**Категория:** Tests & CI · **Impact:** Low · **Effort:** S
**Обоснование:** CI ставит `--frozen-lockfile` (хорошо), но нет отдельного job'а на актуальность/аудит
зависимостей (`pnpm audit`, `pip-audit`). Добавить security-audit шаг для 3 npm- и косвенных python-зависимостей.

### 30. Отсутствуют SECURITY.md, CONTRIBUTING.md, шаблоны issue/PR
**Категория:** Documentation · **Impact:** Low · **Effort:** S
**Обоснование:** Учитывая `_root`-бэкенд и загрузку внешних бинарей, стоит явно описать модель угроз и способ
приватного репорта уязвимостей. Плюс шаблоны PR/issue помогут внешним тестерам, которых требует Decky Store
(`docs/DECKY_STORE.md`).

### 31. `cloud_sync` валидирует `remote`, но не `path` (частичная защита от инъекции)
**Категория:** Security · **Impact:** Med · **Effort:** S
**Обоснование:** `cloud_sync.py::sync_up/sync_down` проверяют `remote` через `_REMOTE_NAME_RE`, но `path`
подставляется в `f"{remote}:{path}"` как есть. Хотя `copy` (а не `sync`) снижает риск удаления, стоит
валидировать/нормализовать `path` (запретить ведущие флаги/`:`), чтобы исключить неожиданные backend-строки.

### 32. Auto-launch и auto-backup регистрируют два независимых `onAppLifecycle`
**Категория:** Performance · **Impact:** Low · **Effort:** S
**Обоснование:** В `index.tsx` `installAutoLaunch` и `installAutoBackup` дважды подписываются на
`RegisterForAppLifetimeNotifications`. Объединить в один слушатель — меньше регистраций в SteamClient и единая
точка обработки жизненного цикла игры.

### 33. Нет мониторинга «умер ли Xvnc/guest» во время сессии
**Категория:** UX / features · **Impact:** Med · **Effort:** M
**Обоснование:** `PipSession` стартует процессы, но не следит за их падением. Если guest упал (частый кейс из
TROUBLESHOOTING — Flatpak-portal), overlay остаётся чёрным без объяснения. Добавить watcher, эмитящий событие в
UI при неожиданном exit любого из процессов.

### 34. `discover_desktop_files` не кэшируется и повторно читает все `.desktop` при каждом сканировании
**Категория:** Performance · **Impact:** Low · **Effort:** S
**Обоснование:** `discovery.py::discover_all` перечитывает все каталоги приложений на каждый клик «Scan».
На Deck это сотни файлов. Кэш с инвалидацией по mtime каталогов ускорит повторные сканы (кнопка «rescan» в
Web-вкладке).

### 35. `store-core.hydrate` не валидирует диапазоны (opacity/geom из чужого импорта)
**Категория:** Bugs / correctness · **Impact:** Low · **Effort:** S
**Обоснование:** `store-core.ts::hydrate` принимает любой `number` для `opacity` и валидный по форме `geom`, но
не клампит их (`presets.clamp` есть, но к hydrate не применяется). Импортированные/битые настройки могут дать
opacity 5000 или geom за экраном. Прогонять через `clamp`/диапазон 20–100.

### 36. Guest-приложения, помеченные `Terminal=true`, оборачиваются в `xterm -e`, но `xterm` больше не ставится
**Категория:** Bugs / correctness · **Impact:** Low · **Effort:** S
**Обоснование:** `discovery.py::parse_desktop_entry` для терминальных `.desktop` формирует `xterm -e <cmd>`,
однако `defaults/install.sh` явно убрал `xterm` из зависимостей. Такие приложения не запустятся. Либо не
предлагать их, либо детектировать наличие `xterm` и предупреждать в UI.

---

## Полный список кандидатов (200)

### Bugs / correctness (32)
1. `updater.run_setup` запускает `setup.sh`, который умирает под root (`id -un != deck`) — one-click update нерабочий.
2. Guest в `session.start` не получает `deck_env()` (нет `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` deck-пользователя).
3. `vncpasswd` пишется root'ом с 0600 и не читается `Xvnc` под `runuser -u deck`.
4. `mpris._dbus_send` не оборачивает `dbus-send` в `runuser`/`deck_env` — под root список плееров всегда пуст.
5. `mirror.find_gamescope_pw_node` вызывает `pw-cli` без deck-окружения — узел gamescope не находится под root.
6. `mirror._spawn_pipeline` запускает gstreamer без `XDG_RUNTIME_DIR` — pipewiresrc не видит сокет deck-пользователя.
7. `vendoring.install_websockify(force=True)` не пересоздаёт wrapper `.real` → PYTHONPATH теряется, импорт падает.
8. `pip-view.PointerCapture` жёстко `top:28`, а `HEADER_TOUCH=50` — мёртвая зона захвата указателя в touch-режиме.
9. `notifications.stop` шлёт `terminate()` только `runuser`, а не группе — `dbus-monitor` зомбируется.
10. `diagnostics._which` не `kill()`-ает процесс при таймауте `--version` — утечка зомби.
11. `diagnostics._which` перехват `(TimeoutError, Exception)` избыточен и глотает все исключения.
12. `SettingsStore.set` без блокировки — потеря апдейтов при параллельных `settings_set`.
13. `store-core.hydrate` не клампит `opacity`/`geom` из импортированных настроек.
14. `discovery.parse_desktop_entry` оборачивает Terminal-приложения в `xterm -e`, но `xterm` не устанавливается.
15. `src/api.ts:31` — два `export const` склеены в одну строку.
16. `stop_pip` в `main.py` удаляет `vncpasswd` повторно (и в `session.stop`, и в `stop_pip`) — избыточно, маскирует ошибки.
17. `cloud_sync.sync_up/down` не валидируют `path` (частичная защита от инъекции backend-строк).
18. `audio.set_guest_volume` клампит до 150, docstring обещает 153 — рассинхрон границ.
19. `session.wait_port` таймаут 5с может быть мал для холодного старта `Xvnc` на слабом APU.
20. `mpris.parse_metadata` может перепутать значение artist, если между key и value нет `variant` (порядок строк dbus).
21. `merge_settings._merge_id_list` дописывает не-dict/без-id элементы в хвост — потенциальные дубликаты при повторном импорте.
22. `battery.read_state` синхронно читает sysfs внутри async `battery_state` без `to_thread` (мелко, но нарушает «async all the way»).
23. `installBatteryWatcher` понижает opacity до 40 при низком заряде, но не восстанавливает прежнее значение при зарядке.
24. `steam.ts` объявляет `RegisterForGameActionStart`, но он нигде не используется — мёртвый интерфейс.
25. `panel.tsx::onSaveProfile` всегда берёт `app_id = profile?.app_id ?? "discord_flatpak"` — профиль может сохранить неверное приложение, если запущено другое.
26. `Content()` читает `__DECKPIP_CURRENT_APPID__` из window один раз в `useEffect([])` — не обновляется при смене игры без переоткрытия панели.
27. `install_everything` помечает `ok=all(...)`, но частичные ошибки не пробрасывают детали в тост (только «open diagnostics»).
28. `notifications.parse_notification_block` берёт `strings[2]/[3]` вслепую — icon-строка со спецсимволами может сместить индексы.
29. `session.url()` кладёт VNC-пароль в query iframe — попадает в любые логи маршрута/histori Steam UI.
30. `_as_user_argv` хардкодит `DECK_USER="deck"` — на не-deck системах (переименованный юзер) drop-privileges ломается.
31. `mirror.start_mirror_window` детектирует падение gst по `sleep(0.5)` — гонка: медленный старт даёт ложный success.
32. `pip-view` drag/resize используют `window.innerWidth/Height` для процентов, но geom клампится к 0–100 без учёта DPI-масштаба Steam UI.

### Security (17)
1. `export_settings` возвращает `github_token` (PAT) — утечка в буфер/`<pre>` через `onExport`.
2. Нет SHA256-верификации скачиваемых архивов noVNC/ludusavi/rclone.
3. `install_websockify` ставит пакет под root без `--require-hashes`.
4. GitHub Actions запинены по плавающим тегам (`@v4`, `@v2`), а не по commit-SHA.
5. `permissions: contents: write` выдан обоим job'ам workflow, хотя нужен только релиз-шагу.
6. `pip-view` iframe: `allow-scripts allow-same-origin` для произвольных внешних URL (Web-PiP/bookmarks).
7. `cloud_sync` не нормализует `path` — теоретическая возможность влиять на назначение rclone.
8. GitHub PAT хранится в `settings.json` в открытом виде без пометки/шифрования.
9. `install_dependencies`/`run_setup` выполняют `pacman`/`setup.sh` под root без подтверждения хэша скриптов.
10. Нет `pnpm audit`/`pip-audit` в CI — уязвимости транзитивных зависимостей не отслеживаются.
11. Нет `dependabot`/`renovate` конфигурации для авто-обновлений безопасности.
12. `_write_vnc_passwd` использует `token[:8]` — 8 символов (ограничение DES VncAuth); стоит явно документировать, что это не крипто-граница (loopback).
13. Пользовательский `command` в custom-app исполняется через argv без allowlist — произвольный бинарь под root/deck (частично осознанно, но нет предупреждения в UI).
14. `notifications`-мост прокидывает текст DM в toaster без ограничения длины на стороне бэкенда (только фронт режет до 200).
15. Диагностика запускает `--version` у ряда бинарей — потенциальный запуск неожиданного исполняемого из PATH при подмене.
16. Нет `Content-Security-Policy`/ограничения на то, какие хосты допускаются в Web-PiP (любой http/https).
17. Загрузки идут по `urllib.request.urlopen` без пиннинга TLS/редирект-политики (доверие только системным CA).

### Performance (14)
1. `settingsSet` дергается на каждый keystroke в text-полях `panel.tsx` (remote/path/hotkey) — нет дебаунса.
2. `installBatteryWatcher` и `installDepsHealthCheck` поллят интервалами даже без активной сессии.
3. `discover_all` перечитывает все `.desktop` каждый скан — нет кэша по mtime.
4. `mpris.list_players` делает 2 последовательных `dbus-send` на плеер (по процессу на вызов) — медленно при многих плеерах.
5. Auto-launch и auto-backup регистрируют два отдельных `onAppLifecycle` вместо одного.
6. `audio._descendant_pids` читает `/proc/*/status` для всех pid при каждом изменении громкости (слайдер шлёт много вызовов).
7. GameMirror-пайплайн `pipewiresrc → videoconvert → ximagesink` копирует кадры через CPU (сам TROUBLESHOOTING признаёт) — нужен GL-путь.
8. Слайдеры Guest volume/Opacity шлют RPC на каждый шаг без throttle.
9. `useStore`/подписки: любой `store.set` уведомляет всех подписчиков, ре-рендеря весь `Content` (40+ state).
10. `checkDeps` в health-check вызывает много `shutil.which` каждую минуту — можно кэшировать между тиками.
11. Нет ленивой инициализации тяжёлых вкладок (Sync/System рендерятся всегда через `Tabs.content`).
12. `PointerCapture.sendMove` троттлит до 33мс, но всё равно создаёт `xdotool`-процесс на каждое движение (дорого).
13. `diagnostics.collect` запускает 9 `--version` подпроцессов параллельно при каждом открытии — можно кэшировать результат.
14. Повторные `listApps()/listBookmarks()` после каждого мелкого действия вместо оптимистичного обновления state.

### Tests & CI (23)
1. Нет `tests/test_diagnostics.py`.
2. Нет `tests/test_ptt.py` (критично: мьют микрофона).
3. Нет eslint/prettier и шага `pnpm run lint` в CI.
4. Нет измерения покрытия (coverage) ни для pytest, ни для vitest.
5. Нет frontend-тестов на `presets.snapToEdges`/`clamp` крайних случаев (есть presets.test.ts, но проверить полноту границ).
6. Нет теста, что `session.start` корректно чистит процессы при частичном фейле (websockify не поднялся).
7. Нет теста на `vendoring.install_websockify` force-переустановку (баг из Bugs #7).
8. Нет теста, что `merge_settings` не теряет `github_token` при merge=false.
9. Нет интеграционного smoke-теста фронтенд-бандла (что `dist/index.js` содержит ожидаемые callable-имена).
10. CI не проверяет соответствие имён callable в `api.ts` методам `Plugin` (легко рассинхронизировать).
11. Нет `pnpm audit`/`pip-audit` job.
12. Нет `concurrency:` в workflow — параллельные пуши гоняют лишние сборки/публикации `dev`.
13. Actions не запинены по SHA (дубль security #4, но и как CI-практика).
14. Нет matrix-прогона pytest на нескольких версиях Python (только 3.11), хотя SteamOS может обновить интерпретатор.
15. Нет теста на `mpris.parse_metadata` при перемешанном порядке dbus-строк.
16. Нет теста на `notifications.parse_notification_block` с icon-строкой, содержащей спецсимволы.
17. Нет проверки, что `defaults/install.sh`/`setup.sh` проходят `shellcheck`.
18. Нет теста на `cloud_sync.parse_remotes` с мусорными строками (частично покрыто — проверить).
19. Нет негативных тестов на `audio.parse_sink_inputs_for_pids` (несколько pid, отсутствие совпадений).
20. Нет CI-артефакта с логами теста при падении (для отладки flaky).
21. Нет проверки типов Python (`mypy`/`pyright`) — только ruff.
22. Нет теста `store-core.hydrate` на клампинг вне-диапазонных значений (после фикса Bugs #13).
23. Нет e2e-заглушки для `steam.ts` shim'ов (проверка graceful-fallback при отсутствии SteamClient).

### Error handling & logging (12)
1. Массовые `.catch(() => {})` во фронтенде скрывают ошибки RPC от пользователя и логов.
2. `diagnostics._which` глушит все исключения (`except Exception`) при получении версии.
3. `install_everything` не отдаёт причину частичного фейла в тост (только «see diagnostics»).
4. Бэкенд использует `decky.logger` крайне скупо — нет логов старта/остановки each process с их pid/argv.
5. `session.start` при `RuntimeError` (порт не поднялся) не логирует stderr `Xvnc`/`websockify`.
6. `mirror`/`mpris`/`audio` возвращают `{"ok": False}` без текста stderr в большинстве веток.
7. Нет уровня логирования/переключателя debug для диагностики на устройстве.
8. `NotificationMirror._reader` глушит исключения `on_notification` без записи в лог.
9. Ошибки парсинга JSON в `import_settings` возвращают generic `invalid_payload` без деталей позиции.
10. `run_setup`/`install_dependencies` обрезают stdout/stderr до 2000 символов без указания, что вывод усечён.
11. Нет единого формата ошибок бэкенда (строки-коды vs структуры) — фронт разбирает эвристиками в `errors.ts`.
12. `friendlyError` не покрывает коды `rate_limited`/`auth_failed`/`not_found` из `updater` — показываются сырыми.

### Architecture / refactor (18)
1. `panel.tsx` (1323 строки) разбить на компоненты-вкладки и хуки.
2. Вынести общий `run_capture(argv, timeout)` для subprocess (`install_dependencies`/`run_setup`/`_run` в ludusavi/cloud_sync).
3. Единый спавнер процессов с `os.setsid`, чтобы `terminate/killpg` работал для всех (session + helpers).
4. `SettingsStore` дать публичные `snapshot()/replace()` вместо `_load`/`_save` с `# noqa: SLF001` в `main.py`.
5. Ввести общий модуль `deckpip/proc.py` (deck_env + as_user + spawn + terminate) — сейчас размазано по session.py.
6. Вынести константы дисплея/портов/geometry в `deckpip/config.py` с загрузкой из настроек.
7. Типизировать ключи настроек (TS union + Python TypedDict) вместо `settingsGet(...) as string`.
8. `Content()` перевести с 40 `useState` на `useReducer`/несколько под-хуков.
9. Абстрагировать «vendored downloader» (noVNC/ludusavi/rclone почти идентичны: download→extract→chmod→resolve).
10. Ввести доменную ошибку `MissingDependency` вместо магических строк `missing_dependency:<x>`.
11. Разнести `api.ts` по фиче-модулям (apps/sync/media/system), сейчас один файл на всё.
12. Слой событий backend→frontend (`decky.emit`) стандартизировать (сейчас только `deckpip_notification`).
13. Вынести управление громкостью/PTT/trackpad в единый «input»-фасад с общим deck-окружением.
14. `PipSession` разделить ответственность: процессный супервизор vs билдер URL/аргументов.
15. Ввести машину состояний сессии (idle→starting→running→paused→stopping) вместо булевых полей.
16. Заменить `window.__DECKPIP_CURRENT_APPID__` на нормальный store-слайс/подписку.
17. Вынести повторяющийся генератор suffix (`crypto.randomUUID().slice(0,8)`), продублированный 4 раза в `panel.tsx`.
18. Инкапсулировать toaster в порт (уже частично есть `toasterPort`) и использовать его везде вместо прямого `toaster.toast`.

### Developer experience / tooling (16)
1. Добавить `Makefile`/`justfile` с целями build/test/lint/pack.
2. Devcontainer/`.tool-versions` для фиксации Node/pnpm/Python.
3. Pre-commit hooks (ruff, prettier, shellcheck) для локальной проверки.
4. `requirements-dev.txt`/pinned ruff+pytest, а не голый `pip install ruff pytest` в CI.
5. Скрипт локального прогона main.py со стабом `decky` (частично есть в тесте — вынести в утилиту).
6. Добавить `pnpm run lint`/`lint:fix`.
7. VS Code recommended-extensions/settings для проекта.
8. Документировать в CONTRIBUTING процесс сборки zip и тестирования на Deck.
9. `mypy`/`pyright` конфиг для строгой типизации бэкенда.
10. Генерация типов callable из одного источника, чтобы `api.ts` и `Plugin` не расходились.
11. Скрипт проверки, что все методы `Plugin` имеют соответствие в `api.ts` (и наоборот).
12. Добавить `EditorConfig`-совместимый prettier-конфиг (indent 2 для ts, 4 для py).
13. Логирование версии плагина при старте (`_main`) для отладки на устройстве.
14. Ввести `--dry-run` для `install.sh`/`setup.sh` (проверка без изменения системы).
15. Скрипт `scripts/dev-sync.sh` для быстрой заливки dist+deckpip на Deck по SSH.
16. Добавить badge статуса CI и покрытия в README.

### Documentation (19)
1. Устранить противоречие public/private в README.
2. Заменить упоминания Xvfb/KasmVNC на Xvnc/TigerVNC во всех доках.
3. Обновить список pacman-зависимостей в `ARCHITECTURE.md` под вендоринг.
4. Исправить «feature branch» → `main` в README/релиз-теле.
5. Документировать реальную callable-поверхность (в `ARCHITECTURE.md` таблица неполная — нет ludusavi/rclone/mpris/trackpad).
6. Добавить SECURITY.md с моделью угроз (`_root`, загрузка бинарей, PAT).
7. Добавить CONTRIBUTING.md.
8. Шаблоны issue/PR в `.github/`.
9. Документировать формат `settings.json` (ключи, типы, ui_state_v1).
10. Описать процедуру ротации/удаления GitHub PAT.
11. Добавить CHANGELOG.md и связать с версионированием (см. Config #25).
12. Задокументировать переменные окружения деплоя (`GITHUB_TOKEN`, `BRANCH`) в setup.sh README-разделе.
13. Обновить `RESEARCH.md` статусы ASSUMED→VERIFIED по мере проверки на железе (сейчас всё ASSUMED).
14. Диаграмма процессов в `ARCHITECTURE.md` использует `Xvnc`, но текст ниже — старые термины; синхронизировать.
15. Документировать ограничение 8-символьного VNC-пароля и почему это ок (loopback).
16. Добавить раздел «производительность/бюджет CPU» с реальными замерами (README «Next steps #6»).
17. Описать поведение auto-backup/auto-cloud-sync и где лежат бэкапы (частично в ludusavi.py docstring — вынести в доку).
18. Пояснить в README, что one-click update сейчас нерабочий/ограничен (до фикса Bugs #1).
19. Документировать матрицу зависимостей фич (какая фича требует какого optional-бинаря).

### UX / features (21)
1. Мониторинг падения Xvnc/guest во время сессии и уведомление пользователя (чёрный iframe → понятная ошибка).
2. Кнопка «Open in Desktop»/копирование URL noVNC для отладки.
3. Индикатор состояния сессии (running/paused) прямо в TitleView, а не только 🔴 при missing deps.
4. Восстанавливать opacity после выхода из low-battery режима (Bugs #23) + тост «restored».
5. Настраиваемый порог low-battery (сейчас хардкод 20%).
6. Настраиваемые DISPLAY/geometry/порты в UI (связано с Config #13) — под внешние мониторы/конфликты.
7. Пресеты позиций дополнить top-left/top-right/center, сейчас только 3.
8. Показывать прогресс/лог загрузки при `install_everything` (сейчас только спиннер-текст).
9. Кнопка «Stop all stray processes» (pkill Xvnc/websockify) — из TROUBLESHOOTING как ручная команда.
10. Поиск/фильтр в списке Apps (есть только для discovered).
11. Подтверждение перед `Restore all saves` (перезапись сейвов) — сейчас без confirm.
12. Отображать размер/дату последнего Ludusavi-бэкапа в Sync-вкладке.
13. Управление громкостью через MPRIS/сектор + отображение обложки трека.
14. Горячая смена приложения без полного stop/start сессии.
15. Быстрый тумблер click-through/visible на самом overlay (не только в панели).
16. Тач-режим: увеличить хит-зоны кнопок MiniBadge/resize (частично есть touchMode, распространить).
17. Индикатор «mic open» при активном PTT (визуальная обратная связь на overlay).
18. Возможность назначить несколько bookmark-групп/иконок.
19. Автозакрытие overlay при выходе из игры (сейчас сессия живёт независимо от игры).
20. Экспорт/импорт настроек через файл (не только clipboard/textarea).
21. Кнопка «Test dependencies for GameMirror» с точечной диагностикой pipewiresrc/wmctrl.

### Config / build (12)
1. Вынести DISPLAY/geometry/порты в конфиг (дубль с UX/Arch — но это про config-слой).
2. Единый источник версии (`package.json`/`plugin.json`/релиз-тег синхронизированы).
3. Добавить поле `version` в `plugin.json`.
4. `concurrency:` в `build.yml` для отмены устаревших сборок.
5. Кэширование скачанных архивов в CI (или в рантайме между force-переустановками).
6. Разделить workflow на lint/test/build/publish job'ы с зависимостями.
7. Пинить версии python-инструментов в CI (ruff/pytest) через requirements.
8. Добавить `prettier`-конфиг и `.prettierignore`.
9. `tsconfig` включает только `src/**` — добавить проверку тестов (`src/__tests__`).
10. Публиковать zip только на тегах/релизах, а не на каждый push в main (сейчас «dev» перезаписывается постоянно).
11. Добавить `.nvmrc`/engines в package.json (Node 20).
12. Явно фиксировать `packageManager` в package.json (pnpm версия для corepack).

### Dependencies & maintenance (9)
1. Настроить `dependabot`/`renovate` для npm и GitHub Actions.
2. Обновлять пины версий вендоримых бинарей (noVNC 1.5.0, ludusavi 0.27.0, rclone 1.69.1, websockify 0.12.0) по расписанию.
3. Добавить `pip-audit`/`pnpm audit` в CI.
4. Зафиксировать minimal `@decky/api`/`@decky/ui` совместимость и проверить upgrade path.
5. Удалить неиспользуемый `@types/webpack` из devDependencies, если бандлит только rollup.
6. Проверить необходимость `happy-dom` версии (20.x) относительно vitest 4.x.
7. Документировать процедуру обновления pnpm-lock и проверки frozen-lockfile.
8. Проверить лицензии транзитивных зависимостей (BSD-3 проект) — добавить license-check.
9. Автоматически проверять доступность URL релизов вендоримых бинарей (dead-link check).

### Accessibility / i18n (7)
1. Все строки UI захардкожены на английском — подключить i18n Decky.
2. Кнопки/иконки (emoji ⏮⏭⏸) без текстовых aria-label — добавить доступные подписи.
3. Overlay drag/resize-ручки без `role`/`aria` и клавиатурной альтернативы.
4. Контраст текста `#888`/`#bbb` на тёмном фоне местами ниже WCAG AA — проверить.
5. `MiniBadge`/resize-handle слишком малы для тач-доступности вне touchMode.
6. Нет поддержки правостороннего чтения/локали для чисел (проценты/размеры).
7. Диагностический `<pre>` не помечен как live-region — скринридер не анонсирует обновление.
</content>
