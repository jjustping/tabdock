# TabDock

**Док из планшета, который лежит без дела: для работы, учёбы и отдыха — с прицелом на фотографов**
· *A work dock made from an idle tablet — for everyday use, built with photographers in mind*

> [!WARNING]
> **Проект в бете.** Сервер — **0.7.0-beta**, Android-клиент **TabDeck — 1.0.0-alpha1**. Всё работает в домашней
> сети, но настройки и API ещё меняются, возможны ошибки. Не для «боевых» каталогов без резервной копии:
> TabDock читает каталог Capture One только для чтения, а звёзды и метки ставит через сам Capture One.
> *Beta: server 0.7.0-beta, Android client TabDeck 1.0.0-alpha1 — things still change and may break.*

[Русский](#русский) · [English](#english) · [Что готово сейчас](#что-готово-сейчас) · [Дорожная карта](#дорожная-карта)

![TabDock — обзор / overview](docs/img/overview.png)

**⬇ [Релизы / Releases](https://github.com/jjustping/tabdock/releases)** — сервер и APK. Нативный клиент TabDeck пока
собирается из `client-android/` (alpha-сборка в релизах появится после проверки записи меток в Capture One).

---

## Русский

**TabDock превращает планшет (или телефон), который лежит без дела, в док для работы на компьютере.**
Это не только для фотографов: при первом запуске вы выбираете сценарии — **Фото**, **Работа**, **Отдых**,
**Система и сеть** — и для каждого получаете своё пространство с виджетами, которые можно переставлять и менять.
Фотографам — больше всего: прогресс обработки съёмок в Capture One (и по папкам для Photon Studio, Photoshop),
отбор, сроки сдачи, галереи клиентов в wfolio, диски и бэкапы каталога.

Всё работает локально в домашней сети: без облака, аккаунтов и подписок (интернет нужен только для погоды
и проверки ссылок wfolio). Сервер — компьютер с macOS 13+ (Linux — в планах), клиент — Android-приложение TabDock
или любой современный браузер на планшете, телефоне или самом компьютере.

### Пространства и виджеты (v0.7)

| | |
|---|---|
| ![Фото](docs/img/spaces/photo.png) | ![Работа](docs/img/spaces/work.png) |
| *Фото: напоминания, съёмки, музыка, быстрые действия, сроки* | *Работа: задачи, заметка-чек-лист, часы, сроки, календарь, фокус-таймер* |
| ![Отдых](docs/img/spaces/fun.png) | ![Система](docs/img/spaces/admin.png) |
| *Отдых: часы, погода, плеер, быстрые действия* | *Система: нагрузка и температура, сеть (роутер, DNS, интернет), диски, кнопки Apple Shortcuts* |

* Пространства переключаются вкладками над виджетами или **свайпом**. Кнопка карандаша — **режим редактирования**:
  переставить виджет, изменить ширину/высоту (сетка 12×6), удалить, «+ Виджет» из каталога, переименовать
  пространство, сменить значок, добавить новое из шаблона.
* **16 виджетов**: напоминания, съёмки, погода+сроки+календарь, музыка, быстрые действия, часы, погода, ближайшие
  сроки, календарь, компьютер, диски, заметка (с чек-листами), фокус-таймер, **сеть**, **команды Apple Shortcuts**,
  галереи wfolio.
* Виджет перерисовывается, только когда изменились его данные (быстрее на планшете), стекло на сенсорных экранах
  размывается легче.

### Первая настройка (v0.7)

| | | |
|---|---|---|
| ![Привет](docs/img/spaces/setup-0.png) | ![Сценарии](docs/img/spaces/setup-1.png) | ![Съёмки](docs/img/spaces/setup-2.png) |

Сценарии → (для фото) где вы обрабатываете и **что считать отданным** → город для погоды → скин → подключение
планшета (QR, пароль). Пройти заново: «Настройки → Пройти первую настройку заново».

### Что ещё умеет

| Блок | Что делает |
|---|---|
| **Напоминания** | Свой список: добавить одной строкой, отметить касанием, срок (сегодня / завтра / дата), ★ важное, теги. Выполненные прячутся. |
| **Съёмки · Capture One** | Читает каталог(и) Capture One **только для чтения**. Каждая съёмка — это альбом: обложка, сколько кадров, сколько отобрано (★ или цветная метка), сколько экспортировано (по истории процессинга), прогресс и статус. Статус, цель (сколько кадров сдать), срок, клиента и заметку можно задать вручную. Можно добавить съёмку вручную, если её нет в каталоге. Кнопка «Открыть в Capture One». |
| **Справка** | Карточки-шпаргалки с простым форматированием (`- список`, `**жирный**`, `` `код` ``), ссылками, цветом, разделами и закреплением. Редактируются с планшета. |
| **Mac** | Загрузка CPU с графиком, температура SoC и SSD (без sudo), память и swap, все диски (внешние можно извлечь), аптайм, IP. |
| **Музыка** | Apple Music / Spotify: что играет, обложка, пауза / назад / вперёд, громкость и mute. |
| **Быстрые действия** | Запуск выбранных приложений (иконки берутся из самих приложений), «Не спать» (caffeinate), скриншот на Рабочий стол, выключить экран, сон (двойное касание для подтверждения), открыть папки. |
| **Погода и календарь** | Погода Open-Meteo (бесплатно, без ключа) на 4 дня; события Календаря macOS на сегодня и завтра. |
| **Подключение** (v0.2) | Отдельная вкладка: вход по QR **или по паролю**, планшет сам ищет TabDock в домашней сети и показывает список, автопереключение, если текущий Mac пропал. |
| **Скины** (v0.6) | Классика, Liquid Glass, Aero · Vista, Aero · Seven, Mac OS X, Бумага, OLED — выбираются в «Настройках» на каждом устройстве, можно задать скин по умолчанию для всех. Иконки нарисованы, без эмодзи. |
| **Каталоги где угодно** (v0.6) | Каталоги ищутся в настройках Capture One (текущий и недавние), Spotlight, «Изображениях» и в корне внешних дисков. По умолчанию — открытый в Capture One; в «Настройках» можно выбрать любые или вписать свой путь. |
| **Съёмки по папкам** (v0.5) | Для редакторов без каталога — Photon Studio, Photoshop и др.: подпапка = съёмка, исходники (RAW) против готовых файлов в подпапке экспорта, рабочие `.photon`/`.psd`, обложка. Настраивается в «Настройках». |
| **«Экспорт закончился»** (v0.5) | Когда Capture One или экспорт в папку перестаёт добавлять файлы, на планшете появляется баннер со звуком: «Свадьба: +24 кадра, 60 из 96». |
| **Ближайшие сроки** (v0.5) | Сдача съёмок, истечение галерей wfolio и напоминания со сроком на 14 дней вперёд — в одном списке на главной. |
| **Чек-листы** (v0.5) | В справке строки `- [ ] пункт` отмечаются касанием; «Снять все отметки» перед следующей съёмкой. |
| **Диски и бэкапы** (v0.5) | Внешние диски: модель, USB/Thunderbolt, файловая система, SMART, свободное место; отметка диска с каталогом и предупреждения «диск с каталогом не подключён», «мало места», «бэкап каталога N дней назад». |
| **Галереи wfolio** (v0.2) | Ссылки на клиентские галереи со сроком хранения: сколько дней осталось, предупреждение за 14 дней, раз в 6 часов док проверяет, открывается ли ссылка. Привязка к съёмке Capture One. |

### Как это работает

![Схема работы](docs/img/diagram.png)
*Планшет и Mac в домашней сети; в интернет уходят только погода и проверка ссылок wfolio.*

### Экраны

![Главная](docs/img/home.png)
*Главная: напоминания, съёмки Capture One с прогрессом, погода и календарь, музыка, быстрые действия.*

![Справка](docs/img/notes.png)
*Справка: свои шпаргалки и ссылки, разделы, цвета, закрепление.*

![Mac](docs/img/mac.png)
*Mac: процессор, температура, память, диски (внешние можно извлечь), системные действия и приложения.*

![Настройки](docs/img/settings.png)
*Настройки: город для погоды, календарь, приложения в быстрых действиях, каталоги Capture One.*

(Все экраны сняты в демо-режиме: съёмки и обложки выдуманные.)

### Темы оформления (скины)

![Все скины](docs/img/skins.png)

Скин выбирается в **«Настройки → Оформление»** и запоминается на каждом устройстве отдельно: на планшете может быть
Aero, а на Mac — «Бумага». Кнопка «Сделать скином по умолчанию для всех» задаёт скин для новых устройств. Для
просмотра без переключения можно открыть адрес с `?skin=glass` (или `aero-vista`, `aero-seven`, `macosx`, `paper`, `oled`).
Во всех скинах — нарисованные иконки, без эмодзи.

| Скин | Настроение |
|---|---|
| **Классика** | тёмная, спокойная — оформление первых версий |
| **Liquid Glass** | полупрозрачное стекло с бликом по краю, мягкий цветной свет, плавающая «капсула» вкладок |
| **Aero · Vista** | Frutiger Aero в духе Windows Vista: чёрное глянцевое стекло, «северное сияние», голубые глянцевые кнопки |
| **Aero · Seven** | Frutiger Aero в духе Windows 7: небо, зелёный холм, пузыри, белое глянцевое стекло, «травяные» индикаторы |
| **Mac OS X** | Aqua 2000-х: полосатый фон, Lucida Grande, глянцевые синие кнопки, каждая карточка — окно со «светофором» |
| **Бумага** | светлый минимализм на каждый день, тёплый белый, чёрные кнопки, один акцент |
| **OLED** | чистый чёрный и монохром — для ночи и OLED-экранов |

![Liquid Glass](docs/img/skins/glass.png)
*Liquid Glass*

![Aero Vista](docs/img/skins/aero-vista.png)
*Aero · Vista*

![Aero Seven](docs/img/skins/aero-seven.png)
*Aero · Seven*

![Mac OS X](docs/img/skins/macosx.png)
*Mac OS X*

![Бумага](docs/img/skins/paper.png)
*Бумага*

![OLED](docs/img/skins/oled.png)
*OLED*

Свой скин — это один CSS-файл в `web/skins/`: он переопределяет переменные (`--bg`, `--card-bg`, `--accent`, `--r`, …)
и при желании добавляет детали. Добавьте его в список `SKINS` в `web/app.js`.

### Установка на компьютер (Mac)

```bash
git clone … ~/tabdock     # или скопируйте папку; не кладите её в Документы/Рабочий стол/Загрузки
cd ~/tabdock
./install.sh
```

`install.sh` создаёт `.venv`, ставит единственную зависимость (`qrcode`), собирает помощник календаря
(`bin/dock-calendar`, нужен `swiftc` из Command Line Tools), регистрирует LaunchAgent
`~/Library/LaunchAgents/com.jjustping.tabdock.plist` (старт при входе в macOS, перезапуск при падении)
и открывает панель в браузере.

```bash
./install.sh --status      # запущен ли и ссылка для планшета
./install.sh --port 9000   # другой порт
./install.sh --uninstall   # убрать автозапуск (данные в data/ остаются)
```

Ручной запуск без автозапуска: `.venv/bin/python server.py` → http://localhost:8787

### TabDeck — нативный клиент для Android (alpha)

`client-android/` — **полностью нативное приложение** (Kotlin + Jetpack Compose), а не страница в оболочке:
все экраны, виджеты, скины, настройки, первая настройка и отбор кадров нарисованы нативно, с сервером оно
общается через тот же API. Работает на планшете (сетка 12×6, как в веб-версии) и на **телефоне** (одна колонка).
Сам находит компьютер в сети (Bonjour + опрос сети), подключается только к компьютеру, который подтвердил ключ,
не даёт экрану гаснуть, переподключается сам. На Android 17 один раз просит разрешение «Устройства в локальной сети»;
если на телефоне включён VPN, старается достучаться до компьютера напрямую через Wi-Fi.

```bash
cd client-android && JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./gradlew assembleRelease
adb install -r app/build/outputs/apk/release/app-release.apk
```

Подписывается тем же ключом, что и старое приложение, поэтому ставится поверх него. Привязать к компьютеру:
открыть ссылку из QR на устройстве или `adb shell am start -d "<ссылка из QR>" com.jjustping.tabdock`.

#### Старое приложение (WebView, `android-webview/`)

Предыдущая версия — оболочка вокруг веб-интерфейса. Оставлена для истории, её заменяет TabDeck.
`android-webview/` — маленькое приложение (28 КБ) с WebView, которое
* **само находит Mac** через Bonjour (`_tabdock._tcp`) и опросом сети — браузер так не умеет;
* открывается на весь экран, **не даёт экрану гаснуть**, держит альбомную ориентацию;
* помнит последний Mac и вход; если Mac выключили или перезагрузили — показывает «Жду …» и **сам
  открывает панель**, как только Mac снова в сети; если пропал совсем — переходит на другой найденный TabDock;
* ссылки наружу (галереи wfolio и т.п.) открывает в обычном браузере.

Готовый APK — в [релизах](https://github.com/jjustping/tabdock/releases/latest): скачайте на планшет, откройте,
разрешите установку из этого источника и нажмите «Установить».

Сборка без Android Studio и Gradle (нужны Android SDK и JDK 17, `brew install openjdk@17`):

```bash
./android-webview/build.sh               # → android-webview/build/TabDock.apk
adb install -r android-webview/build/TabDock.apk
```

Ключ подписи создаётся при первой сборке в `~/.android/tabdock-release.keystore` — сохраните его, иначе
обновить приложение поверх не получится (только удалить и поставить заново). Первый вход в приложении —
паролем, или передать ключ из QR: `adb shell am start -n com.jjustping.tabdock/.MainActivity -d "<ссылка из QR>"`.

### Подключение планшета

![Вход на планшете](docs/img/login.png)
*Вход на планшете: пароль слева, справа TabDock, найденные в сети автоматически.*

![Подключение](docs/img/connect.png)
*Вкладка «Подключение»: QR-код, пароль, ключ доступа, список Mac в сети и автоподключение.*

1. Планшет и Mac в одной сети.
2. На Mac нажмите ▦ (вверху справа) — появится QR-код.
3. Отсканируйте камерой планшета и откройте ссылку в Chrome. Планшет запомнится (cookie на год).
4. В Chrome: меню ⋮ → «Добавить на главный экран» — панель откроется на весь экран, как приложение.

**Без QR — по паролю и поиску (v0.2).** На Mac: вкладка «Подключение» → «Пароль для входа» (или
`.venv/bin/python server.py --set-password`). На планшете откройте адрес Mac (например `http://192.168.1.50:8787`):
появится страница входа — пароль слева, справа список TabDock, которые планшет нашёл в сети сам
(опрашивает `/api/hello` на всех адресах вида 192.168.x.1–254, ~15 с). Нажмите на нужный — перейдёте к нему.

* Пароль хранится только как хэш PBKDF2; менять его можно только с самого Mac; 5 неверных попыток → пауза 5 минут.
* Сервер объявляет себя по Bonjour как `_tabdock._tcp` (браузер Bonjour не видит, поэтому планшет ищет опросом).
* «Автоподключение»: если текущий Mac пропал из сети больше чем на 15 с, планшет сам переходит на другой
  найденный TabDock.
* Ограничение браузера: самый первый адрес нужно открыть хотя бы раз (QR или вручную) — веб-страница не может
  искать в сети, пока она не открыта. Закрепите за Mac mini постоянный IP в роутере, чтобы ярлык не ломался.

Без ключа или пароля чужие устройства в сети видят только страницу входа. «Подключение → Новый ключ»
отключает все ранее подключённые устройства. С самого Mac (localhost) вход не нужен.

### wfolio

![Галереи wfolio](docs/img/wfolio.png)
*Галереи wfolio: сколько дней хранения осталось, открывается ли ссылка, к какой съёмке привязана.*

У wfolio **нет открытого API**, вебхуков или выгрузки со сроками хранения (проверено по документации
docs.wfolio.pro 6 ноября 2026; CSV-выгрузка проекта содержит только избранное, без дат). Поэтому:

* галерея добавляется вручную: ссылка, срок хранения (как в настройках проекта wfolio), клиент, съёмка;
* док сам раз в 6 часов открывает ссылку: ● открывается / ● «Срок действия ссылки истёк» (или 404) / ● нет ответа;
* за 14 дней до конца срока на главной появляется предупреждение;
* логин и пароль wfolio **не нужны и не хранятся**.

Автоматически подтягивать список галерей можно было бы, только «притворяясь браузером» в личном кабинете
wfolio с вашей сессией — это хрупко и не одобрено wfolio, поэтому не сделано.

### Безопасность (v0.4)

* **Только частные сети.** Сервер отвечает только адресам домашних сетей (192.168.x, 10.x, 172.16–31.x, localhost);
  запросы из интернета (если кто-то пробросит порт) получают отказ.
* **Защита от чужих сайтов.** Страница в браузере на Mac или планшете не может ничего сделать в TabDock: POST-запросы
  принимаются только как JSON с того же адреса (защита от CSRF), запросы с подменённым именем хоста
  отклоняются (защита от DNS rebinding).
* **Пароль**: хэш PBKDF2, менять можно только с самого Mac, 5 ошибок с одного адреса или 20 всего — пауза 5 минут.
* **Планшет в чужом Wi-Fi.** Приложение для Android запоминает «отпечаток» вашего Mac при первом подключении
  (trust on first use). Затем при каждом запуске Mac должен доказать, что знает общий секрет (запрос-ответ
  HMAC; сам ключ по сети не передаётся). Само приложение открывает **только подтверждённый Mac**; сервер с тем же
  именем или адресом, но без ключа, показан как «⚠ не подтверждён», и перед его открытием приложение стирает
  ваш вход для этого адреса — пароль и ключ к чужому серверу не уйдут.
* В браузерной версии автопереключение на другой сервер выключено по умолчанию (браузер не умеет проверять ключ).
* Ссылки в заметках — только `http(s)`, `mailto`, `tel`.

Что ещё стоит сделать — в разделе «Дальше».

### Разрешения macOS (один раз)

Служба запускается через маленькое приложение **TabDock.app** (`bin/TabDock.app`, собирается `install.sh`), поэтому
в настройках конфиденциальности разрешения выдаются ему, а не безымянному Python. Если каталог Capture One лежит
на внешнем диске: Системные настройки → Конфиденциальность и безопасность → Полный доступ к диску → «+» →
`~/tabdock/bin/TabDock.app`. После пересборки TabDock.app разрешение может понадобиться выдать заново.


macOS спросит разрешения у `python3` при первом обращении — нажмите «Разрешить»:

| Что | Зачем | Где включить вручную |
|---|---|---|
| Папка «Изображения» | читать каталог Capture One в `~/Pictures` | Настройки → Конфиденциальность → Файлы и папки (или «Полный доступ к диску» для python3, если каталог на внешнем диске) |
| Календари | события на главной | Конфиденциальность → Календари (`dock-calendar` или python3) |
| Автоматизация → Music / Spotify / Calendar | плеер и (запасной путь) календарь | Конфиденциальность → Автоматизация |
| Запись экрана | кнопка «Скриншот» | Конфиденциальность → Запись экрана |

Если календарь не нужен — «Настройки → Календарь → Выключить».

### Как считается прогресс съёмок

![Съёмки](docs/img/shoots.png)
*Съёмки: статус, прогресс экспорта, сколько кадров отобрано и выгружено, срок wfolio.*

* **Съёмка** = пользовательский альбом в каталоге (служебные «Недавние импорты» пропускаются).
  Если альбомов нет, съёмками считаются импорты.
* **Экспортировано** = кадры, у которых есть запись в истории процессинга (вывода) Capture One.
* **Цель** = отобранные кадры (рейтинг ★1+ или любая цветная метка); если отбора нет — все кадры.
  Можно задать вручную (например, «сдать 40»).
* **Статус** автоматически: *Не начато* → *Отбор* (есть отобранные, ничего не выгружено) →
  *В работе* → *Готово*. Вручную можно поставить любой, в том числе *Сдано*.
* Каталоги ищутся сами (Spotlight + `~/Pictures`). Свой список — поле `c1_catalogs` в `data/config.json`.
* Сами правки (экспозиция и т.п.) в базе Capture One 16 надёжно не отмечаются, поэтому «обработано»
  определяется по экспорту.
* **Отбор с планшета** (TabDeck → съёмка → «Отбор и метки»): сетка миниатюр с фильтрами (без оценки, ★1+, ★3+,
  не экспортированы, по цвету) и просмотр на весь экран со свайпом. Звёзды и цветные метки записываются
  **через AppleScript самого Capture One** — база каталога не трогается. Нужно, чтобы каталог был открыт в
  Capture One, и один раз разрешить «TabDock → Capture One» в окне «Автоматизация».
  Миниатюры — из кэша Capture One (с правками), большой просмотр — встроенный в RAW снимок камеры
  (для Fuji RAF мгновенно, остальное декодирует macOS).

### Данные и устройство

```
server.py            HTTP-сервер (stdlib), API и раздача web/
dock/sysinfo.py      CPU (mach host_statistics), память (vm_stat), диски (df), сеть
dock/temps.py        температуры Apple Silicon через IOHIDEventSystem (ctypes, без sudo)
dock/media.py        Music/Spotify и громкость через AppleScript
dock/captureone.py   чтение каталога .cocatalog (sqlite, mode=ro)
dock/calendar_mac.py календарь: bin/dock-calendar (EventKit) или AppleScript
dock/weather.py      Open-Meteo
web/                 интерфейс (HTML/CSS/JS без сборки)
data/                ваши данные: config.json, reminders.json, notes.json, shoots.json
```

Логи службы: `~/Library/Logs/TabDock/`.

**Демо-режим для скриншотов:** `.venv/bin/python server.py --demo --port 8788 --data /tmp/tabdock-demo` —
выдуманные съёмки с обложками-заглушками, календарь и «Mac mini»; настоящий каталог не читается.
Добавьте `?privacy=1` к адресу, чтобы размыть обложки и ключ в QR. Все картинки в `docs/img` сняты так.

### Что проверено, а что нет (v0.4, 6 ноября 2026)

v0.4, безопасность: доказательство ключа в `/api/hello` (ключ не утекает), отказ при чужом Host (421),
отказ cross-site POST и не-JSON POST (403), отбрасывание `javascript:`-ссылок. **На планшете:** обновление поверх
0.3 сохранило вход и запомнило Mac; подменный сервер на том же адресе с другим ключом показан
«⚠ не подтверждён» и не открылся сам; после возврата настоящего сервера панель открылась сама.
Не проверено: доступ из публичной сети (отказ по адресу клиента проверен только кодом), два настоящих Mac.


v0.3, Android-приложение — **на настоящем Honor Pad 9** (Android 14): установка через adb, приложение само нашло
MacBook в сети и открыло вход; вход по ключу; после перезапуска приложения вход сохраняется; без сервера —
экран «Жду …», после запуска сервера панель открылась сама. Веб-версия в Chrome на планшете тоже проверена
(полный экран по первому касанию). Не проверено: переход на другой Mac, работа после перезагрузки планшета.

v0.2 (подключение и wfolio), на MacBook Air M1: пароль (задать только с Mac, вход, неверный пароль, блокировка
после 5 попыток — HTTP 429), страница входа с LAN-адреса, поиск в сети (headless Firefox нашёл оба запущенных
сервера на :8787 и :8788 за 13 с), Bonjour-объявление (`dns-sd -B _tabdock._tcp`), галереи wfolio: добавление,
проверка ссылки (200 → «открывается», 404 → «истекла»), отбраковка неправильных ссылок.
Не проверено: автопереключение на другой Mac при реальном пропадании сервера, поиск с самого планшета,
настоящая ссылка wfolio (текст «Срок действия ссылки истёк» взят из документации wfolio).

v0.1:

Проверено на **MacBook Air M1** (macOS 15.7), запуск вручную:
* сервер, API (напоминания, заметки, съёмки, действия с проверкой допустимых значений), ключ доступа
  (без ключа — 401, по ссылке из QR — cookie);
* чтение реального каталога Capture One (3 альбома, обложки, экспорт 163/163);
* температуры, CPU, память, диски, громкость, погода; интерфейс в браузере 1280×800.

**Не проверено:**
* на самом Mac mini M4 и на планшете Honor Pad 9 (нужно сопряжение Wi-Fi-отладки);
* `install.sh` и LaunchAgent целиком (синтаксис и plist проверены, но установка не запускалась);
* доступ к Календарю: на MacBook доступа пока нет — нужен ответ на запрос macOS;
* обложка и управление при реально играющей Music/Spotify; Spotify не установлен;
* сеансы Capture One (`.cosessiondb`) — сейчас поддерживаются только каталоги.

### Что готово сейчас

Состояние на 7 ноября 2026. ✅ — работает и проверено на настоящих устройствах (Mac mini M4, Honor Pad 9, Pixel 8);
🧪 — сделано, но проверено не до конца; ⏳ — в планах.

| Часть | Статус |
|---|---|
| Сервер на macOS: автозапуск, поиск в сети (Bonjour), ключ + пароль, защита от чужих сетей | ✅ |
| Пространства и 16 виджетов, режим редактирования, 7 скинов | ✅ |
| Съёмки Capture One: прогресс, статусы, сроки, правило «что считать отданным» (метка / экспорт / рейтинг), каталоги на внешних дисках | ✅ |
| Съёмки по папкам (Photon Studio, Photoshop и др.) | 🧪 на реальных съёмках ещё не проверено |
| Музыка, громкость, быстрые действия, Apple Shortcuts, погода, календарь, сеть, диски | ✅ |
| **TabDeck** — нативный Android-клиент: все экраны, настройки и первая настройка нативные | ✅ alpha |
| Раскладка для **телефона** | ✅ первая версия (Pixel 8) |
| **Отбор с планшета/телефона**: миниатюры, просмотр на весь экран, фильтры | ✅ |
| Запись ★ и цветных меток в Capture One (через его AppleScript) | 🧪 написано, запись ещё не подтверждена на живом каталоге |
| Android 17: разрешение «локальная сеть», обход VPN для домашней сети | ✅ / 🧪 обход VPN |
| Старое WebView-приложение (`android-webview/`) | заменяется TabDeck |
| Значок в строке меню, конструктор тем, Linux, публикация в магазинах | ⏳ |

### Дорожная карта

| Этап | Что будет |
|---|---|
| ~~0.7 beta~~ | ✅ пространства и виджеты, первая настройка, правило «отдано», виджеты «Сеть» и «Команды» |
| **0.8** (сейчас) | ✅ нативный клиент TabDeck, ✅ отбор с метками, ✅ раскладка для телефона; осталось: подтвердить запись меток в Capture One, **значок в строке меню** на сервере (статус, перезапуск службы), alpha-релиз TabDeck с APK |
| 0.9 | режим «подставки» для телефона; **конструктор тем** в приложении (свои цвета, стекло, фон из обложки съёмки), импорт/экспорт тем; офлайн-кэш и уведомления в TabDeck (экспорт закончился, срок сдачи) |
| 1.0 | **сервер на Linux**: systemd, MPRIS-плееры, датчики, darktable/digiKam, значок в трее, `install-linux.sh`; первый стабильный релиз; **публикация TabDeck в RuStore** (и, возможно, Google Play) |
| дальше | Lightroom Classic, сеансы Capture One, tether viewer для X-T4, виджеты на экране Android, несколько компьютеров в одном доке, HTTPS и ключи на устройство |

Windows пока не планируется (оценка — [docs/WINDOWS.md](docs/WINDOWS.md)).

**Безопасность (рекомендации)**
* HTTPS с самоподписанным сертификатом, отпечаток которого приложение запоминает при подключении.
* Отдельный ключ на каждое устройство со списком и отзывом; подтверждение нового устройства на компьютере.
* Bonjour и доступ только в домашних сетях (для ноутбука, который носят с собой).

## English

**TabDock turns an idle tablet (or phone) into a work dock for your computer** — for everyday work, study and
fun, built with photographers in mind. On first launch you pick usage scenarios (**Photo**, **Work**, **Fun**,
**System & network**); each becomes a space of widgets you can rearrange. Photographers get the most: Capture One
(and folder-based Photon Studio / Photoshop) editing progress, culling, deadlines, wfolio galleries, disks and catalog
backups. Local network only, no cloud. Server: macOS 13+ (Linux planned); client: the Android app or any browser.

**Status: beta.** Server 0.7.0-beta, native Android client **TabDeck 1.0.0-alpha1**. Ready and tested on real devices:
spaces & 16 widgets, 7 skins, Capture One progress with a configurable "delivered" rule, native TabDeck client
(tablet + phone layouts), culling from the tablet/phone (thumbnails, full-screen viewer, filters). Done but not fully
verified: writing stars/colour tags back through Capture One's AppleScript, folder-based shoots, VPN bypass.
Planned: menu-bar icon, theme builder, Linux server, store releases (RuStore) at 1.0.

![Spaces](docs/img/spaces/work.png)

### Features

* **Reminders**: its own list. Quick add, tap to complete, due dates, ★ important, tags.
* **Shoots · Capture One**: reads Capture One catalogs **read-only**. Each user album is a shoot,
  with a cover, total / picked (★ or colour tag) / exported (from the process history), progress and
  status. You can set the status, target, deadline, client and a note by hand, add manual shoots, and
  open a shoot in Capture One.
* **Reference**: cheat-sheet cards with light markdown, links, colours, sections and pins. Editable
  from the tablet.
* **Mac**: CPU with a sparkline, SoC/SSD temperatures (no sudo), memory/swap, disks (eject external
  ones), uptime, IP.
* **Music**: Apple Music / Spotify now playing, artwork, transport controls, volume and mute.
* **Quick actions**: launch your apps, keep-awake (caffeinate), screenshot, display off, sleep
  (tap twice to confirm), open folders.
* **Weather & calendar**: Open-Meteo forecast (free, no key) and today's/tomorrow's macOS Calendar
  events.
* **Connect tab (v0.2)**: sign in with the QR code **or a password**. The login page finds TabDock servers on
  the LAN by itself (it probes `/api/hello` across the /24 subnet; the server also advertises Bonjour
  `_tabdock._tcp`) and can fail over to another server automatically.
* **v0.6**: skins (Classic, Liquid Glass, Aero Vista, Aero Seven, Mac OS X, Paper, OLED) with drawn icons instead of
  emoji; Capture One catalogs anywhere (Capture One prefs, Spotlight, ~/Pictures, external disk roots), chooser in Settings.
* **v0.5**: folder-based shoots for Photon Studio / Photoshop (RAW vs exported files), "export finished" banner with
  a chime, upcoming deadlines (shoots, wfolio expiry, reminders), tappable checklists in notes, external disk details
  (model, bus, file system, SMART) with catalog-disk and catalog-backup warnings.
* **wfolio galleries (v0.2)**: wfolio has no public API, so you add gallery links with their storage end date.
  The dock checks every link every 6 hours (active / expired) and warns 14 days ahead. No wfolio credentials are
  used.

### How it works

![How it works](docs/img/diagram.png)
*Tablet and Mac on the home network; only the weather and wfolio link checks go to the internet.*

### Screens (demo data)

![Home](docs/img/home.png)
*Home: reminders, Capture One shoots with progress, weather & calendar, music, quick actions.*

![Shoots](docs/img/shoots.png)
*Shoots: status, export progress, picked/exported counts, wfolio expiry.*

![wfolio](docs/img/wfolio.png)
*wfolio galleries: days of storage left, link alive or expired, linked shoot.*

![Reference](docs/img/notes.png)
*Reference: your own cheat sheets and links.*

![Mac](docs/img/mac.png)
*Mac: CPU, temperature, memory, disks, system actions and apps.*

![Settings](docs/img/settings.png)
*Settings: weather city, calendar, quick-action apps, Capture One catalogs.*

### Skins

![All skins](docs/img/skins.png)

Pick a skin in **Settings → Appearance**; it is remembered per device (Aero on the tablet, Paper on the Mac), and one
can be set as the default for new devices. Preview without switching: add `?skin=glass` (or `aero-vista`, `aero-seven`,
`macosx`, `paper`, `oled`) to the address. All skins use drawn line icons, no emoji.

* **Classic** — the original dark look.
* **Liquid Glass** — translucent glass with specular edges over soft colour, floating tab capsule.
* **Aero · Vista** / **Aero · Seven** — Frutiger Aero: black glossy glass with aurora; sky, grass, bubbles and glossy white glass.
* **Mac OS X** — 2000s Aqua: pinstripes, Lucida Grande, glossy blue buttons, every card is a window with traffic lights.
* **Paper** / **OLED** — everyday minimal, light and true-black.

A skin is one CSS file in `web/skins/` overriding theme variables; register it in `SKINS` in `web/app.js`.

### Install

```bash
cd ~/tabdock && ./install.sh        # venv + calendar helper + LaunchAgent, opens the dashboard
./install.sh --status | --uninstall | --port 9000
```

Keep the folder outside Desktop/Documents/Downloads: background agents can't read those.
To run it by hand: `.venv/bin/python server.py` → http://localhost:8787

### Android app

**TabDeck** (`client-android/`, alpha) is a fully native Kotlin + Jetpack Compose client: every screen, widget, skin,
settings, first-run setup and culling are native; tablet and phone layouts; Bonjour + subnet discovery, key pinning,
Android 17 local-network permission, Wi-Fi-bound connections when a VPN is on. Build with
`cd client-android && ./gradlew assembleRelease` (JDK 17).

The old WebView shell lives in `android-webview/`: a tiny (28 KB) WebView app that finds the Mac by itself (Bonjour `_tabdock._tcp` + subnet probe),
runs fullscreen, keeps the screen on, remembers the last Mac and sign-in, reopens the dock by itself when the Mac
comes back, and fails over to another TabDock. Build without Gradle: `./android-webview/build.sh` (Android SDK + JDK 17),
then `adb install -r android-webview/build/TabDock.apk`. Ready-made APK: [latest release](https://github.com/jjustping/tabdock/releases/latest). Keep `~/.android/tabdock-release.keystore` to be able to update.

### Pair the tablet

![Login](docs/img/login.png)
*Tablet login: password on the left, TabDock servers found on the LAN on the right.*

![Connect](docs/img/connect.png)
*Connect tab: QR code, password, access key, servers on the LAN, auto-connect.*

Press ▦ on the Mac, scan the QR code with the tablet, then in Chrome use ⋮ → "Add to Home screen".
Devices without the key only see a "not paired" page. *Settings → New key* revokes all paired devices.

### Security (v0.4)

Private networks only; same-origin JSON POSTs (CSRF) and Host-header checks (DNS rebinding); PBKDF2 password with
rate limits. The Android app pins your Mac on first pairing (TOFU) and then requires an HMAC challenge-response
on every start: it auto-opens only a verified Mac, marks look-alikes as "not verified" and wipes your sign-in
cookie before opening one, so credentials never go to an unknown server on a foreign Wi-Fi.
Planned: HTTPS with a pinned self-signed certificate, per-device keys with revocation, approving new devices on the Mac.

### Roadmap

**0.8 (now)**: ✅ native TabDeck client, ✅ culling with stars/tags, ✅ phone layout; left: confirm tag writing in
Capture One, menu-bar status icon, TabDeck alpha release · 0.9 phone "stand" mode, in-app theme builder, offline cache
and notifications · 1.0 Linux server (systemd, MPRIS, sensors, darktable/digiKam, tray icon), first stable release,
**TabDeck on RuStore** (maybe Google Play) · later: Android home-screen widgets, Lightroom Classic, Capture One sessions, X-T4 tether viewer, multiple computers, HTTPS.
Windows is not planned for now ([docs/WINDOWS.md](docs/WINDOWS.md)).

### macOS permissions

The first time, macOS asks to allow `python3` access to Pictures (for the Capture One catalog),
Calendars, Automation (Music/Spotify/Calendar) and Screen Recording (for the screenshot button).
Click Allow, or turn them on in System Settings → Privacy & Security.

### Tested / not tested (v0.3)

Tested on a MacBook Air M1 (macOS 15.7), started by hand: the server, the API, key auth, reading a
real Capture One catalog, sensors, volume, weather, and the UI at 1280×800.
On a real Honor Pad 9 (Android 14): the web UI in Chrome (fullscreen on first tap) and the Android app
(finds the Mac by itself, keeps the sign-in after restart, reopens the dock when the server comes back).
Also: password login, LAN scan, Bonjour advertising, wfolio link checks.
**Not tested yet**: the Mac mini itself, the full `install.sh`/LaunchAgent run, failover to another Mac,
a playing Music/Spotify track, and Capture One sessions (only catalogs are supported).

License: MIT.
