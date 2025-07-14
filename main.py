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
            with open(self.data_file, 'r') as f:
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

# Flask server to keep alive
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Website monitoring service is running."

@app.route('/health')
def health():
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "monitored_sites": len(WEBSITES)
    }

# Websites list
WEBSITES = [
    {
        'name': '18 СОУ - Свободни места',
        'url': 'https://18sou.net/%D1%81%D0%B2%D0%BE%D0%B1%D0%BE%D0%B4%D0%BD%D0%B8-%D0%BC%D0%B5%D1%81%D1%82%D0%B0/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '32-ро - Свободни места',
        'url': 'https://school32.com/%d0%bf%d1%80%d0%b8%d0%b5%d0%bc/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': 'СМГ - Свободни места',
        'url': 'https://smg.bg/razni/2024/03/11/8622/svobodni-mesta-za-priem-na-uchenitsi-v-10-klas-za-vtori-srok-na-uchebnata-2023-2024-godina/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': 'НПМГ - Прием в старши класове',
        'url': 'https://npmg.org/%d0%bf%d1%80%d0%b8%d0%b5%d0%bc-%d0%b2-%d1%81%d1%82%d0%b0%d1%80%d1%88%d0%b8-%d0%ba%d0%bb%d0%b0%d1%81%d0%be%d0%b2%d0%b5/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '1-ва Английска Sofia - Свободни места',
        'url': 'https://www.fels-sofia.org/bg/svobodni-mesta-236',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '2-ра Английска - Свободни места',
        'url': 'https://2els.com/%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F-%D0%B7%D0%B0-%D1%81%D0%B2%D0%BE%D0%B1%D0%BE%D0%B4%D0%BD%D0%B8-%D0%BC%D0%B5%D1%81%D1%82%D0%B0',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '90 СОУ - Прием',
        'url': 'https://sou90.org/priem/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '22 СЕУ - Свободни места',
        'url': 'https://22seu.org/%D1%81%D0%B2%D0%BE%D0%B1%D0%BE%D0%B4%D0%BD%D0%B8-%D0%BC%D0%B5%D1%81%D1%82%D0%B0-%D0%B7%D0%B0-%D1%83%D1%87%D0%B5%D0%BD%D0%B8%D1%86%D0%B8/',
        'selector': '.entry-content, .content, main, article'
    },
    # NEW SCHOOLS ADDED:
    {
        'name': '1 СОУ София - Свободни места',
        'url': 'https://1sousofia.org/?page_id=7673',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '2 СУ - Свободни места',
        'url': 'https://2su.bg/%D1%81%D0%B2%D0%BE%D0%B1%D0%BE%D0%B4%D0%BD%D0%B8-%D0%BC%D0%B5%D1%81%D1%82%D0%B0',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '10 СОУ - Свободни места',
        'url': 'https://10sou.eu/%d0%bf%d1%80%d0%b8%d0%b5%d0%bc/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '12 СОУ София - Свободни места',
        'url': 'https://12sou-sofia.info/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0-%d0%b2-%d0%bd%d0%b0%d1%87%d0%b0%d0%bb%d0%b5%d0%bd-%d0%b8-%d0%bf%d1%80%d0%be%d0%b3%d0%b8%d0%bc%d0%bd%d0%b0%d0%b7%d0%b8/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '30 СУ - Свободни места',
        'url': 'https://30su-bg.com/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '36 СОУ - Прием',
        'url': 'https://36sou.com/priem/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '68 СУ - Свободни места',
        'url': 'https://68su.org/2025/07/07/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0-%d0%bf%d0%be-%d0%bf%d0%b0%d1%80%d0%b0%d0%bb%d0%b5%d0%bb%d0%ba%d0%b8-%d1%96-x%d1%96%d1%96-%d0%ba%d0%bb%d0%b0-8/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '119 СУ - Свободни места',
        'url': 'https://119su.bg/bg/svobodni-mesta',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': '127 СОУ - Свободни места',
        'url': 'https://127sou.com/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0/',
        'selector': '.entry-content, .content, main, article'
    },
    {
        'name': 'Еврейско училище - Свободни места',
        'url': 'https://www.hebrewschool-bg.org/2025/07/08/%d1%81%d0%b2%d0%be%d0%b1%d0%be%d0%b4%d0%bd%d0%b8-%d0%bc%d0%b5%d1%81%d1%82%d0%b0-%d0%b7%d0%b0-%d1%83%d1%87%d0%b5%d0%bd%d0%b8%d1%86%d0%b8/',
        'selector': '.entry-content, .content, main, article'
    }
]

def run_monitor():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    monitor = WebsiteMonitor(bot_token, chat_id)
    
    # 🚀 NEW: Schedule monitoring at fixed UTC times
    schedule.every().day.at("06:03").do(lambda: monitor.check_all_websites(WEBSITES))
    schedule.every().day.at("12:03").do(lambda: monitor.check_all_websites(WEBSITES))
    schedule.every().day.at("17:03").do(lambda: monitor.check_all_websites(WEBSITES))
    
    # Send startup notification
    monitor.send_telegram_message(
        f"🎓 <b>Мониторинг стартиран</b>\n"
        f"Проверявам {len(WEBSITES)} училища в 06:03, 12:03 и 17:03 UTC за свободни места.\n"
        f"Време на стартиране: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} UTC"
    )
    
    logging.info("📅 Scheduled monitoring at 06:03, 12:03, and 17:03 UTC")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ✅ Start background monitor thread on startup
threading.Thread(target=run_monitor, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"🚀 Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port)
