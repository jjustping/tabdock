# Как помочь TabDock

Ошибки и идеи — в [Issues](https://github.com/jjustping/tabdock/issues). Принцип проекта: удобный док для компьютера, а не
приложение «умею всё, но плохо», поэтому новые функции сначала обсуждаем.

## Разработка

Сервер — Python 3.9+ на стандартной библиотеке (и `qrcode`), macOS или Linux:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # тесты (нужна команда openssl)
.venv/bin/python server.py --demo      # демо-данные вместо реальных съёмок
```

Приложение — Kotlin и Compose в `client-android/`, нужен JDK 17: `./gradlew assembleRelease`.

Устройство кода: `dock/core.py` — приложение и операции, `dock/httpd.py` — HTTP и проверки доступа, `dock/linux/` — части для
Linux, остальные файлы в `dock/` — отдельные функции.

## Перед отправкой изменений

- Тесты проходят, новая логика и проверки доступа покрыты тестами.
- В репозитории и на скриншотах только демо-данные: никаких имён клиентов, реальных фото, ключей и домашних адресов.
- Базу каталога Capture One можно только читать, запись — только через AppleScript самого Capture One.
- Изменения для пользователей описаны в `CHANGELOG.md`.
