# TabDock для Windows — план

*Статус: только план (ноябрь 2026). Кода для Windows ещё нет.*
*English summary at the end.*

## Что уже переносимо, а что завязано на macOS

| Часть | Сейчас | Для Windows |
|---|---|---|
| HTTP-сервер, API, хранилище `data/`, пароль, ключ, CSRF/Host-проверки | Python stdlib | **работает как есть** |
| Веб-интерфейс, страница входа, поиск в сети | HTML/JS | **как есть**; слово «Mac» → «компьютер» по флагу платформы |
| Android-приложение, проверка ключа Mac | Java | **как есть** (сервер отвечает тем же `/api/hello`) |
| Погода, wfolio, QR | Python | **как есть** |
| Чтение каталога Capture One | SQLite | **как есть**, другой путь поиска каталогов (см. ниже) |
| Статус: CPU, память, диски, сеть, аптайм | `host_statistics`, `vm_stat`, `df`, `sysctl`, `route` | `psutil` (кроссплатформенный, можно и на Mac) |
| Температура | IOHID (Apple Silicon) | нет стандартного API: WMI `MSAcpi_ThermalZoneTemperature` часто пуст и требует админа; LibreHardwareMonitor ставит драйвер. **Предлагаю: на Windows показывать «—»** или брать из LibreHardwareMonitor, если он запущен (его веб-сервер/WMI) |
| Музыка и громкость | AppleScript Music/Spotify | **GSMTC** (Global System Media Transport Controls через пакет `winsdk`): «сейчас играет» и управление для любого плеера — Spotify, браузер, Apple Music для Windows; громкость — `pycaw` (Core Audio) |
| Запуск приложений и иконки | `open -a`, `.icns` → `sips` | ярлыки из меню «Пуск» (`.lnk` в `%ProgramData%` и `%AppData%\…\Start Menu`), запуск `os.startfile`; иконки — извлечь из `.exe` (`pywin32` + Pillow) или пропустить на первом этапе |
| Сон / выключить экран / скриншот / «не спать» / извлечь диск | `pmset`, `screencapture`, `caffeinate`, `diskutil` | `SetSuspendState` (осторожно: при включённой гибернации уйдёт в неё); `SendMessage(SC_MONITORPOWER)`; `mss`/Pillow `ImageGrab`; `SetThreadExecutionState`; глагол «Извлечь» через `Shell.Application` (PowerShell) |
| Календарь | Swift + EventKit | системного календаря для обычных программ нет (Outlook — через COM, только если установлен). **Предлагаю ICS-подписку** (Google/iCloud/Outlook дают ссылку `.ics`) — работает и на Mac, и на Windows |
| Bonjour (`_tabdock._tcp`) | утилита `dns-sd` | пакет **`zeroconf`** (чистый Python) — заменить на обеих системах; Windows 10+ сам умеет mDNS |
| Автозапуск | LaunchAgent | **Планировщик заданий**, триггер «при входе пользователя», `pythonw.exe` (без окна). Не служба Windows: службы работают в «сеансе 0» и не могут управлять музыкой, экраном и программами пользователя |
| Установка | `install.sh` | `install.ps1`: venv, зависимости, задание планировщика, правило брандмауэра; позже — один `.exe` (PyInstaller) и установщик (Inno Setup) |
| Брандмауэр | — | при первом запуске Windows спросит доступ; правило только для профиля **«Частная сеть»** (в «Общедоступной» сети сервер будет закрыт — это совпадает с политикой «только домашние сети») |
| Логи и данные | `~/Library/Logs/TabDock`, папка проекта | `%LOCALAPPDATA%\TabDock\` |

### Фоторедакторы на Windows
* **Capture One**: каталог по умолчанию `%USERPROFILE%\Pictures\Capture One Catalog.cocatalog`. Формат базы
  тот же SQLite, но **на Windows-каталоге не проверено** — нужен пример каталога. Поиск: `Pictures` + список путей в
  настройках (вместо Spotlight).
* **Lightroom Classic**: `%USERPROFILE%\Pictures\Lightroom\Lightroom Catalog.lrcat` (SQLite, как на Mac) — модуль
  Lightroom из плана будет общим.
* **Photoshop / Photon Studio**: через папки, как на Mac (Photon Studio от Tenzen тоже есть для Windows).

## Как устроить код
`dock/platform/` с одинаковым интерфейсом: `sysinfo`, `temps`, `media`, `actions`, `autostart`, `calendar`.
`mac.py` — нынешний код, `windows.py` — новый; сервер выбирает по `sys.platform`. В `/api/state` добавить
`platform`, чтобы интерфейс показывал «Компьютер»/«Windows» вместо «Mac» и прятал недоступное (температура).

## Оценка (рабочие дни)
| Шаг | Дни |
|---|---|
| Вынести платформенный слой, `zeroconf` вместо `dns-sd` (полезно и для Mac) | 1 |
| Статус через `psutil` | 0,5 |
| Музыка (GSMTC) и громкость (`pycaw`) | 1 |
| Быстрые действия, ярлыки «Пуска», иконки | 1–1,5 |
| Автозапуск, `install.ps1`, брандмауэр | 1 |
| Календарь через ICS (для обеих систем) | 0,5 |
| Пути Capture One/Lightroom на Windows + проверка на настоящем каталоге | 0,5–1 |
| Тесты, CI, README | 1 |
| **Итого** | **≈ 6–8 дней** до паритета (без температуры) |

## Как тестировать без своего Windows
1. **Parallels Desktop уже стоит на этом Mac** → Windows 11 для ARM в виртуалке (мастер Parallels скачивает
   его сам; для тестов можно без активации). Python для Windows ARM64 есть; если какой-то пакет (`winsdk`) не
   соберётся под ARM64 — x64-Python работает в эмуляции. Сеть виртуалки — режим **«Мост» (Bridged)**, иначе
   планшет её не увидит.
2. **GitHub Actions, раннер `windows-latest`**: автотесты на каждый коммит — запуск сервера, `/api/hello`, пароль,
   проверки безопасности, `psutil`-статус, чтение тестового каталога SQLite. Звук/экран/музыку на раннере
   не проверить. В приватном репозитории бесплатно 2000 минут в месяц, минуты Windows считаются ×2.
3. Whisky/Wine на Mac для этого **не подходит** (не настоящий Windows, нет GSMTC/WMI).
4. Перед релизом — 1–2 добровольца с настоящим Windows-ПК и Capture One/Lightroom.

---

## English summary
Portable today: the Python server and API, security, web UI, Android app, weather, wfolio, Capture One SQLite reader.
macOS-only: system stats (→ `psutil`), temperatures (→ none / LibreHardwareMonitor), media (→ GSMTC via `winsdk`,
volume via `pycaw`), quick actions (→ Start-menu shortcuts, `SetSuspendState`, `SetThreadExecutionState`, `mss`),
calendar (→ ICS subscription for both OSes), Bonjour (→ `zeroconf` for both), autostart (→ Task Scheduler at logon,
not a Windows service), installer (→ `install.ps1`, later PyInstaller + Inno Setup), firewall rule for the Private
profile only. Catalogs: Capture One `Pictures\Capture One Catalog.cocatalog`, Lightroom
`Pictures\Lightroom\Lightroom Catalog.lrcat`. Effort ≈ 6–8 working days. Testing: Windows 11 ARM in Parallels
(bridged network), GitHub Actions `windows-latest` for automated tests, plus real-PC beta testers.
