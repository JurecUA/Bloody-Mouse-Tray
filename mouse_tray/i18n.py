"""Small runtime translation catalog for the user interface."""

# Translation keys and their localized values read better as complete phrases.
# ruff: noqa: E501

from __future__ import annotations

LANGUAGES = {"en": "English", "ru": "Русский", "uk": "Українська"}

_TRANSLATIONS = {
    "ru": {
        "Language": "Язык", "English": "Английский", "Русский": "Русский", "Українська": "Украинский", "settings": "настройки",
        "Appearance": "Внешний вид", "System": "Система", "Dark theme": "Тёмная тема",
        "Settings and About dialogs": "Окна настроек и сведений", "Battery icon": "Иконка батареи",
        "Glyph instead of digits": "Иконка вместо цифр", "Text outline": "Обводка текста",
        "Keeps digits readable": "Цифры остаются читаемыми", "Color by charge level": "Цвет по уровню заряда",
        "Yellow and red when low": "Жёлтый и красный при низком заряде", "Colors": "Цвета",
        "Text size": "Размер текста", "Digits in the tray icon": "Цифры в значке трея", "Font": "Шрифт",
        "All fonts": "Все шрифты", "Monospaced": "Моноширинный", "System font": "Системный шрифт",
        "Start with Windows": "Запускать вместе с Windows", "Run at sign-in": "Запуск при входе в систему",
        "Poll interval": "Интервал опроса", "Seconds between reads": "Секунд между опросами",
        "Debug logging": "Журнал отладки", "Write logs/app.log next to the program": "Записывать logs/app.log рядом с программой",
        "Defaults": "По умолчанию", "Open log": "Открыть журнал", "Cancel": "Отмена", "OK": "ОК",
        "Reset timer": "Сбросить таймер", "Settings...": "Настройки...", "About...": "О программе...", "Exit": "Выход",
        "Battery": "Батарея", "No Mouse Detected": "Мышь не обнаружена", "Charging": "Заряжается", "Charged 100%": "Заряжена на 100%",
        "Full": "Полный заряд", "just now": "только что", " d ago": " дн. назад", " h ago": " ч назад", " min ago": " мин назад", "Normal": "Обычный",
        " days, ": " дн., ", "About": "О программе", "Supported device:": "Поддерживаемое устройство:",
        "Supported devices:": "Поддерживаемые устройства:", "Based on Fan4Metal/mouse_tray": "На основе Fan4Metal/mouse_tray",
        "Invalid font": "Некорректный шрифт", "Could not load font {face}.\nPlease choose another.": "Не удалось загрузить шрифт {face}.\nВыберите другой.",
        "Could not change the autostart setting:\n{error}": "Не удалось изменить настройку автозапуска:\n{error}",
        "Dark Fluent look for the settings and about windows.\nTurn off for a light palette. Switches this dialog live;\nsaved when you press OK.": "Тёмное оформление окон настроек и сведений.\nВыключите, чтобы использовать светлую тему. Изменение\nприменяется сразу и сохраняется после нажатия ОК.",
        "Draw a battery filled to the charge level instead of\nthe percent digits. The exact number moves to the\ntray tooltip.": "Показывать батарею с уровнем заряда вместо\nпроцентов. Точное значение будет в подсказке\nзначка в трее.",
        "Draw a contrasting outline around the tray digits and\nthe report-rate icon. Keeps them readable on a same-colored taskbar.": "Добавить контрастную обводку цифрам и значку частоты,\nчтобы они оставались видны на панели задач любого цвета.",
        "Scale the tray digits.\n100% fills the icon; lower values shrink.": "Изменить размер цифр в трее.\nПри 100% значок заполнен; меньшие значения уменьшают цифры.",
        "List every installed font, not just monospaced ones.\nThe digits are measured in the chosen face, so any font fits.": "Показывать все установленные шрифты, а не только моноширинные.\nЦифры подгоняются под выбранный шрифт.",
        "Open log (exists only after Debug logging was on).": "Открыть logs/app.log (создаётся при включённой отладке).",
        "Could not load font {face!r}.\nPlease choose another.": "Не удалось загрузить шрифт {face!r}.\nВыберите другой.",
        "Full {age}": "Полный заряд: {age}",
        "Battery and report-rate indicator for the Bloody SG5 Pro (8K) wireless mouse in the Windows system tray. Portable: settings live next to the program.": "Индикатор заряда и частоты опроса беспроводной мыши Bloody SG5 Pro (8K) в системном трее Windows. Портативная версия: настройки хранятся рядом с программой.",
        "Shows the charge in the tray; the tooltip adds the report rate, DPI and the time since the last full charge.\nHover the icon to see the report rate (125 ... 1K ... 8K) in the color of the mouse's own indicator.\nPortable: settings and the full-charge date are stored next to the program (a log only while Debug logging is on); the only registry entry is the optional \"Start with Windows\" value.\nWorks without Bloody Central running.": "Показывает заряд в трее; в подсказке указаны частота опроса, DPI и время с последней полной зарядки.\nНаведите курсор на значок, чтобы увидеть частоту (125 ... 1K ... 8K) в цвете индикатора мыши.\nПортативная версия: настройки и дата полной зарядки хранятся рядом с программой; журнал создаётся только при включённой отладке. В реестр добавляется только необязательная запись автозапуска.\nРаботает без запущенной Bloody Central.",
        "Color the battery percent by charge: font color above {mid}%, then the two picked colors at ≤ {mid}% and ≤ {low}%.": "Цвет процентов зависит от заряда: основной цвет выше {mid}%, затем выбранные цвета при ≤ {mid}% и ≤ {low}%.",
        "Run the program when you sign in to Windows. Stored as a Run value\nfor the current user that points at this copy of the program;\npress OK with the switch on after moving the folder to refresh it.": "Запускать программу при входе в Windows. Путь к этой копии\nхранится в разделе автозапуска текущего пользователя. После\nперемещения папки нажмите ОК при включённом переключателе.",
        "Off by default: no log file is written at all.\nTurn it on, press OK, and attach the file when reporting a problem.": "По умолчанию журнал не создаётся. Включите запись, нажмите ОК\nи приложите файл при сообщении о проблеме.",
    },
    "uk": {
        "Language": "Мова", "English": "Англійська", "Русский": "Російська", "Українська": "Українська", "settings": "налаштування",
        "Appearance": "Вигляд", "System": "Система", "Dark theme": "Темна тема",
        "Settings and About dialogs": "Вікна налаштувань і відомостей", "Battery icon": "Іконка батареї",
        "Glyph instead of digits": "Іконка замість цифр", "Text outline": "Контур тексту",
        "Keeps digits readable": "Цифри залишаються читабельними", "Color by charge level": "Колір за рівнем заряду",
        "Yellow and red when low": "Жовтий і червоний за низького заряду", "Colors": "Кольори",
        "Text size": "Розмір тексту", "Digits in the tray icon": "Цифри в значку трея", "Font": "Шрифт",
        "All fonts": "Усі шрифти", "Monospaced": "Моноширинний", "System font": "Системний шрифт",
        "Start with Windows": "Запускати разом із Windows", "Run at sign-in": "Запуск під час входу",
        "Poll interval": "Інтервал опитування", "Seconds between reads": "Секунд між опитуваннями",
        "Debug logging": "Журнал налагодження", "Write logs/app.log next to the program": "Записувати logs/app.log поруч із програмою",
        "Defaults": "За замовчуванням", "Open log": "Відкрити журнал", "Cancel": "Скасувати", "OK": "Гаразд",
        "Reset timer": "Скинути таймер", "Settings...": "Налаштування...", "About...": "Про програму...", "Exit": "Вийти",
        "Battery": "Батарея", "No Mouse Detected": "Мишу не виявлено", "Charging": "Заряджається", "Charged 100%": "Заряджено на 100%",
        "Full": "Повний заряд", "just now": "щойно", " d ago": " дн. тому", " h ago": " год тому", " min ago": " хв тому", "Normal": "Звичайний",
        " days, ": " дн., ", "About": "Про програму", "Supported device:": "Підтримуваний пристрій:",
        "Supported devices:": "Підтримувані пристрої:", "Based on Fan4Metal/mouse_tray": "На основі Fan4Metal/mouse_tray",
        "There is no log yet: it is written only while Debug logging is on.\nTurn it on, press OK and use the program for a while.": "Журналу ще немає: він створюється, лише коли ввімкнено налагодження.\nУвімкніть його, натисніть «Гаразд» і трохи скористайтеся програмою.",
        "Invalid font": "Некоректний шрифт", "Could not load font {face}.\nPlease choose another.": "Не вдалося завантажити шрифт {face}.\nВиберіть інший.",
        "Could not change the autostart setting:\n{error}": "Не вдалося змінити налаштування автозапуску:\n{error}",
        "Dark Fluent look for the settings and about windows.\nTurn off for a light palette. Switches this dialog live;\nsaved when you press OK.": "Темне оформлення вікон налаштувань і відомостей.\nВимкніть, щоб використовувати світлу тему. Зміна\nдіє одразу й зберігається після натискання «Гаразд».",
        "Draw a battery filled to the charge level instead of\nthe percent digits. The exact number moves to the\ntray tooltip.": "Показувати батарею з рівнем заряду замість\nвідсотків. Точне значення буде в підказці\nзначка в треї.",
        "Draw a contrasting outline around the tray digits and\nthe report-rate icon. Keeps them readable on a same-colored taskbar.": "Додати контрастний контур цифрам і значку частоти,\nщоб вони залишалися видимими на панелі завдань будь-якого кольору.",
        "Scale the tray digits.\n100% fills the icon; lower values shrink.": "Змінити розмір цифр у треї.\nЗа 100% значок заповнений; менші значення зменшують цифри.",
        "List every installed font, not just monospaced ones.\nThe digits are measured in the chosen face, so any font fits.": "Показувати всі встановлені шрифти, а не лише моноширинні.\nЦифри підлаштовуються під вибраний шрифт.",
        "Open log (exists only after Debug logging was on).": "Відкрити logs/app.log (створюється за ввімкненого налагодження).",
        "Could not load font {face!r}.\nPlease choose another.": "Не вдалося завантажити шрифт {face!r}.\nВиберіть інший.",
        "Full {age}": "Повний заряд: {age}",
        "Battery and report-rate indicator for the Bloody SG5 Pro (8K) wireless mouse in the Windows system tray. Portable: settings live next to the program.": "Індикатор заряду та частоти опитування бездротової миші Bloody SG5 Pro (8K) у системному треї Windows. Портативна версія: налаштування зберігаються поруч із програмою.",
        "Shows the charge in the tray; the tooltip adds the report rate, DPI and the time since the last full charge.\nHover the icon to see the report rate (125 ... 1K ... 8K) in the color of the mouse's own indicator.\nPortable: settings and the full-charge date are stored next to the program (a log only while Debug logging is on); the only registry entry is the optional \"Start with Windows\" value.\nWorks without Bloody Central running.": "Показує заряд у треї; у підказці наведено частоту опитування, DPI та час від останнього повного заряджання.\nНаведіть курсор на значок, щоб побачити частоту (125 ... 1K ... 8K) у кольорі індикатора миші.\nПортативна версія: налаштування й дата повного заряджання зберігаються поруч із програмою; журнал створюється лише за ввімкненого налагодження. До реєстру додається лише необов’язковий запис автозапуску.\nПрацює без запущеної Bloody Central.",
        "Color the battery percent by charge: font color above {mid}%, then the two picked colors at ≤ {mid}% and ≤ {low}%.": "Колір відсотків залежить від заряду: основний колір вище {mid}%, потім вибрані кольори за ≤ {mid}% і ≤ {low}%.",
        "Run the program when you sign in to Windows. Stored as a Run value\nfor the current user that points at this copy of the program;\npress OK with the switch on after moving the folder to refresh it.": "Запускати програму під час входу у Windows. Шлях до цієї копії\nзберігається в розділі автозапуску поточного користувача. Після\nпереміщення папки натисніть «Гаразд» за ввімкненого перемикача.",
        "Off by default: no log file is written at all.\nTurn it on, press OK, and attach the file when reporting a problem.": "За замовчуванням журнал не створюється. Увімкніть запис, натисніть\n«Гаразд» і додайте файл до повідомлення про проблему.",
    },
}


def tr(message: str, language: str = "en", **values: object) -> str:
    """Translate a UI message, falling back to English for incomplete catalogs."""
    translated = _TRANSLATIONS.get(language, {}).get(message, message)
    return translated.format(**values) if values else translated

