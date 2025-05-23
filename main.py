import os
import requests
import hashlib
import time
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import schedule
import threading
from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)

class WebsiteMonitor:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.data_file = 'website_states.json'
        self.load_previous_states()

    def load_previous_states(self):
        try:
            with open(self.data_file, ' 'r') as f:
                self.previous_states = json.load(f)
        except FileNotFoundError:
            self.previous_states = {}

    def save_states(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.previous_states, f, indent=2)

    def get_page_content(self, url, selector=None):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
            }
            session = requests.Session()
            session.headers.update(headers)
            response = session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            if selector:
                elements = soup.select(selector)
                fallback_selectors = ['.post-content', '.page-content', '.entry', 'main', 'article']
                if not elements:
                    for fallback in fallback_selectors:
                        elements = soup.select(fallback)
                        if elements:
                            break
                content = ' '.join([e.get_text(strip=True) for e in elements])
            else:
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                content = soup.get_text()

            return ' '.join(content.split())
        except Exception as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def get_content_hash(self, content):
        return hashlib.md5(content.encode('utf-8')).hexdigest() if content else None

    def send_telegram_message(self, message):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {'chat_id': self.chat_id, 'text': message, 'parse_mode': 'HTML'}
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            logging.info("Telegram message sent.")
        except Exception as e:
            logging.error(f"Telegram error: {e}")

    def check_website(self, url, name, selector=None):
        logging.info(f"Checking {name} ({url})")
        current_content = self.get_page_content(url, selector)
        if not current_content:
            return

        current_hash = self.get_content_hash(current_content)
        previous_hash = self.previous_states.get(url)

        if not previous_hash:
            self.previous_states[url] = current_hash
            logging.info(f"{name}: baseline saved.")
        elif current_hash != previous_hash:
            self.previous_states[url] = current_hash
            message = (
    f"🎓 <b>Нови свободни места!</b>\n\n"
    f"<b>Училище:</b> {name}\n"
    f"<b>Линк:</b> {url}\n"
    f"<b>Време:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
)
            self.send_telegram_message(message)
        else:
            logging.info(f"{name}: no change.")
        self.save_states()

    def check_all_websites(self, websites):
        logging.info("Running check cycle...")
        for site in websites:
            self.check_website(site['url'], site['name'], site.get('selector'))
            time.sleep(2)
        logging.info("Check cycle done.")

app = Flask(__name__)

WEBSITES = [
    {'name': '18 СОУ - Свободни места', 'url': 'https://18sou.net/свободни-места/', 'selector': '.entry-content, .content, main, article'},
    {'name': 'School32 - Свободни места', 'url': 'https://school32.com/прием/свободни-места/', 'selector': '.entry-content, .content, main, article'},
    {'name': 'SMG - Свободни места', 'url': 'https://smg.bg/razni/2024/03/11/8622/svobodni-mesta-za-priem-na-uchenitsi-v-10-klas-za-vtori-srok-na-uchebnata-2023-2024-godina/', 'selector': '.entry-content, .content, main, article'},
    {'name': 'NPMG - Прием в старши класове', 'url': 'https://npmg.org/прием-в-старши-класове/', 'selector': '.entry-content, .content, main, article'},
    {'name': 'FELS Sofia - Свободни места', 'url': 'https://www.fels-sofia.org/bg/svobodni-mesta-236', 'selector': '.entry-content, .content, main, article'},
    {'name': '2 ЕЛС - Свободни места', 'url': 'https://2els.com/информация-за-свободни-места', 'selector': '.entry-content, .content, main, article'},
    {'name': '90 СОУ - Прием', 'url': 'https://sou90.org/priem/', 'selector': '.entry-content, .content, main, article'},
    {'name': '22 СЕУ - Свободни места', 'url': 'https://22seu.org/свободни-места-за-ученици/', 'selector': '.entry-content, .content, main, article'}
]

def run_monitor():
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        interval = int(os.getenv("CHECK_INTERVAL", 480))

        monitor = WebsiteMonitor(bot_token, chat_id)

        monitor.send_telegram_message(
            f"🎓 <b>Мониторинг стартиран</b>
Проверявам {len(WEBSITES)} училища на всеки {interval} минути за свободни места."
        )

        monitor.check_all_websites(WEBSITES)
        schedule.every(interval).minutes.do(lambda: monitor.check_all_websites(WEBSITES))

        while True:
            schedule.run_pending()
            time.sleep(60)
    except Exception as e:
        logging.error(f"Monitor crashed: {e}")

def start_background_monitor():
    thread = threading.Thread(target=run_monitor, daemon=True)
    thread.start()

start_background_monitor()

@app.route('/')
def home():
    return "✅ Website monitoring service is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
