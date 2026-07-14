import os
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin

# === Настройки ===
BASE_URL = "https://src.infinitewave.ca/"
LOG_FILE = "download.log"
PROXY = None  # Замени на "socks5://118.113.245.55:2324", если нужен прокси

# === Настройка логирования ===
logging.basicConfig(
    filename=LOG_FILE,
    format="%(asctime)s | %(message)s",
    level=logging.INFO,
    encoding="utf-8"
)
logger = logging.getLogger()

def write_log(message):
    logger.info(message)
    print(message)

def decode_and_normalize(raw_bytes):
    """
    Пытается декодировать сырые байты как UTF-8. 
    Если файл содержит спецсимволы другой кодировки, откатывается на cp1252.
    Затем нормализует переносы строк под стандарт LF (\n).
    """
    try:
        # Пробуем прочитать как правильный UTF-8
        print("Распознали как UTF-8")
        text = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        # Если не вышло — читаем как Windows-1252
        print("Распознали как UTF-8")
        text = raw_bytes.decode('cp1252')
        
    # Нормализуем окончания строк
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    filtered_lines = [line for line in lines if "iso-8859-1" not in line.lower()]
    return '\n'.join(filtered_lines)


def download_file(url, folder, filename, session):
    """Функция скачивания отдельного файла с проверкой на существование"""
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, filename)
    
    if os.path.exists(file_path):
        write_log(f"Файл существует: {file_path} — пропускаем.")
        return
        
    try:
        response = session.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            
            # Проверяем, текстовый ли это файл
            if filename.lower().endswith(('.html', '.css', '.xml', '.js', '.txt')):
                # Читаем сразу сырые байты файла в память
                raw_bytes = response.content
                # Прогоняем через нашу умную функцию
                normalized_text = decode_and_normalize(raw_bytes)
                
                # Сохраняем текст в UTF-8 с LF-переносами
                with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(normalized_text)
            else:
                # Для картинок и zip-архивов оставляем потоковое бинарное скачивание
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                            
            write_log(f"Успешно сохранён: {file_path}")
        else:
            write_log(f"Ошибка HTTP {response.status_code} при загрузке: {url}")
    except Exception as e:
        write_log(f"Ошибка соединения для {url}: {e}")

def main():
    write_log("Начинаем создание оффлайн-версии...")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL
    })
    
    # Подключение прокси
    if PROXY:
        if PROXY.startswith("socks5://"):
            session.proxies = {
                "http": f"socks5h://{PROXY[9:]}",
                "https": f"socks5h://{PROXY[9:]}",
            }
        else:
            session.proxies = {"http": PROXY, "https": PROXY}
            
    # 1. Скачиваем и сохраняем главную страницу
    write_log("Загружаем index.html...")
    main_page_resp = session.get(BASE_URL)
    
    # Используем ту же функцию для обработки главной страницы
    main_html = decode_and_normalize(main_page_resp.content)
    
    with open("index.html", "w", encoding="utf-8", newline='\n') as f:
        f.write(main_html)
        
    # 2. Парсим HTML
    soup = BeautifulSoup(main_html, 'html.parser')
    
    # 3. Вытаскиваем все уникальные файлы конвертеров и категории
    tpack_select = soup.find('select', {'name': 'tPack'})
    tmode_select = soup.find('select', {'name': 'tMode'})
    
    # Используем set, чтобы убрать дубликаты
    filenames = list(set([opt.get('value') for opt in tpack_select.find_all('option') if opt.has_attr('value')]))
    modes = [opt.get('value') for opt in tmode_select.find_all('option') if opt.has_attr('value')]
    
    write_log(f"Найдено {len(filenames)} уникальных конвертеров и {len(modes)} режимов.")
    
    # 4. Генерируем URL и качаем все графики в соответствующие папки
    for mode in modes:
        for filename in filenames:
            img_url = urljoin(BASE_URL, mode + filename)
            folder = os.path.join(".", os.path.normpath(mode))
            download_file(img_url, folder, filename, session)

    # 5. Скачиваем статические файлы
    static_files = [
        # Графика и скрипты главной страницы
        "images/Loading.png",
        "images/MagsChart.png", 
        "images/BlankChart.jpg",
        "images/MenuBG.jpg",
        "images/Social.jpg",
        "images/Header.jpg",
        "images/BGPlate2.jpg",
        "images/SweepImg.jpg",
        "images/ToneImg.jpg",
        "images/PassbandImg.jpg",
        "images/TransitionImg.jpg",
        "images/PhaseImg.jpg",
        "images/Impulse.png",
        "favicon.ico",
        "IW1.js",
        
        # Информационные страницы
        "faq.html",
        "help.html",
        "crdt.html",
        "srcrss.xml",
        "mainFF.css",
        "mainIE.css",
        
        # Архив с тестовыми сигналами
        "TestSignals.zip"
    ]
    
    write_log("Загружаем статические файлы сайта...")
    for static_file in static_files:
        url = urljoin(BASE_URL, static_file)
        folder = os.path.join(".", os.path.dirname(static_file)) if os.path.dirname(static_file) else "."
        filename = os.path.basename(static_file)
        download_file(url, folder, filename, session)
        
    write_log("Все файлы успешно загружены! Папка готова к заливке на GitHub Pages.")

if __name__ == "__main__":
    main()