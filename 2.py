import requests
from bs4 import BeautifulSoup
from flask import Flask
import threading
import time

app = Flask(__name__)

TOKEN = "8127921766:AAFJBcEYYX6UhPjyZFG7-cC5_H8bb72Q_GA"
CHAT_ID = "1905948782"
HEADERS = {"User-Agent": "Mozilla/5.0"}
CHECK_INTERVAL = 900  # каждые 15 минут

sent_links = set()
first_run = True
parser_started = False

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=payload)
        if not response.ok:
            print(f"Ошибка Telegram: {response.text}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")

def extract_info(detail):
    address = ""
    area = ""
    price = ""

    for p in detail.find_all("p"):
        if "Hamburg" in p.text:
            address = p.text.strip()
            break

    for tag in detail.find_all():
        text = tag.get_text(strip=True)
        if "Wohnfläche" in text or "Жилая площадь" in text:
            area = text
        if "Miete" in text or "Базовая аренда" in text:
            price = text

    return address, area, price

def parse_dawonia():
    global sent_links, first_run
    count = 0
    base_url = "https://www.dawonia.de"
    url = f"{base_url}/de/mieten"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Ошибка загрузки Dawonia: {res.status_code}")
        return 0
    soup = BeautifulSoup(res.text, "html.parser")
    links = soup.select("span[data-href]")

    for tag in links:
        href = tag.get("data-href")
        if not href or not href.startswith("/de/real-estate"):
            continue
        full_url = base_url + href
        if full_url in sent_links:
            continue

        ad_page = requests.get(full_url, headers=HEADERS)
        if ad_page.status_code != 200:
            continue
        ad_soup = BeautifulSoup(ad_page.text, "html.parser")
        detail = ad_soup.find("div", class_="c-object-detail-info__inner")
        if not detail:
            continue

        immomio_links = ad_soup.select("a[href*='immomio']")
        if not immomio_links:
            continue

        address, area, price = extract_info(detail)
        if "Hamburg" not in address:
            continue

        message = (
            f"<b>Dawonia</b>\n"
            f"<a href='{immomio_links[0]['href']}'>Ссылка на immomio</a>\n"
            f"🏠 {address}\n"
            f"📏 {area}\n"
            f"💶 {price}"
        )
        send_telegram(message)
        sent_links.add(full_url)
        count += 1

    if first_run and count == 0:
        send_telegram("Dawonia: пока нет квартир в Hamburg.")
    return count

def parse_saga():
    global sent_links, first_run
    count = 0
    url = "https://www.saga.hamburg/immobiliensuche?Kategorie=APARTMENT"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Ошибка загрузки Saga: {res.status_code}")
        return 0
    soup = BeautifulSoup(res.text, "html.parser")
    offers = soup.select("a[href*='immomio']")

    for tag in offers:
        link = tag.get("href")
        if link in sent_links:
            continue
        message = f"<b>Saga</b>\n<a href='{link}'>Ссылка на immomio</a>"
        send_telegram(message)
        sent_links.add(link)
        count += 1

    if first_run and count == 0:
        send_telegram("Saga: пока нет новых ссылок.")
    return count

def parse_immowelt():
    global sent_links, first_run
    count = 0
    search_url = "https://www.immowelt.de/liste/hamburg/wohnungen/mieten"
    res = requests.get(search_url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Ошибка загрузки Immowelt: {res.status_code}")
        return 0
    soup = BeautifulSoup(res.text, "html.parser")
    offers = soup.select("a[href*='immomio']")

    for a in offers:
        href = a.get("href")
        if href in sent_links:
            continue
        message = f"<b>Immowelt</b>\n<a href='{href}'>Ссылка на immomio</a>"
        send_telegram(message)
        sent_links.add(href)
        count += 1

    if first_run and count == 0:
        send_telegram("Immowelt: пока нет новых ссылок.")
    return count

def parser_loop():
    global first_run
    while True:
        print("🔍 Проверка новых квартир...")
        total = 0
        total += parse_saga()
        total += parse_dawonia()
        total += parse_immowelt()
        # Можно вернуть parse_immoscout позже
        print(f"✅ Найдено новых ссылок: {total}")
        first_run = False
        time.sleep(CHECK_INTERVAL)

@app.route('/')
def home():
    return "🏡 Бот по поиску квартир работает!"

def start_parser():
    global parser_started
    if not parser_started:
        parser_started = True
        threading.Thread(target=parser_loop).start()

if __name__ == '__main__':
    start_parser()
    app.run(host='0.0.0.0', port=8080)