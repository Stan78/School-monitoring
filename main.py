import os
import requests
import hashlib
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import threading
from flask import Flask, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Flask app
app = Flask(__name__)

class WebsiteMonitor:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.previous_states = {}
        self.last_check = None
        self.check_count = 0
        self.status = "Initializing..."
        logging.info("WebsiteMonitor initialized")
        
    def get_page_content(self, url, selector=None):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            if selector:
                elements = soup.select(selector)
                if not elements:
                    fallback_selectors = ['.post-content', '.page-content', '.entry', 'main', 'article']
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
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logging.info("Telegram message sent successfully")
            return True
        except Exception as e:
            logging.error(f"Telegram error: {e}")
            return False

    def check_website(self, url, name, selector=None):
        logging.info(f"Checking {name}")
        current_content = self.get_page_content(url, selector)
        if not current_content:
            return False

        current_hash = self.get_content_hash(current_content)
        previous_hash = self.previous_states.get(url)

        if not previous_hash:
            self.previous_states[url] = current_hash
            logging.info(f"{name}: baseline established")
            return True
        elif current_hash != previous_hash:
            self.previous_states[url] = current_hash
            message = (
                f"🎓 <b>Нови свободни места!</b>\n\n"
                f"<b>Училище:</b> {name}\n"
                f"<b>Линк:</b> {url}\n"
                f"<b>Време:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            self.send_telegram_message(message)
            logging.info(f"{name}: CHANGE DETECTED!")
            return True
        else:
            logging.info(f"{name}: no changes")
            return True

    def check_all_websites(self, websites):
        self.status = "Checking websites..."
        logging.info("=== Starting check cycle ===")
        successful_checks = 0
        
        for site in websites:
            try:
                if self.check_website(site['url'], site['name'], site.get('selector')):
                    successful_checks += 1
                time.sleep(2)
            except Exception as e:
                logging.error(f"Error checking {site['name']}: {e}")
        
        self.last_check = datetime.now()
        self.check_count += 1
        self.status = f"Active - Last check: {self.last_check.strftime('%H:%M:%S')}"
        
        logging.info(f"=== Check cycle complete: {successful_checks}/{len(websites)} successful ===")
        return successful_checks

    def get_status(self):
        return {
            'status': self.status,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'check_count': self.check_count,
            'monitored_sites': len(WEBSITES)
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
    }
]

# Global monitor instance
monitor = None

def initialize_monitor():
    global monitor
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        logging.info(f"Bot token exists: {bool(bot_token)}")
        logging.info(f"Chat ID exists: {bool(chat_id)}")
        
        if not bot_token or not chat_id:
            logging.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
            return None
            
        monitor = WebsiteMonitor(bot_token, chat_id)
        logging.info("Monitor initialized successfully")
        return monitor
    except Exception as e:
        logging.error(f"Error initializing monitor: {e}")
        return None

def monitoring_loop():
    try:
        global monitor
        logging.info("Starting monitoring loop...")
        
        if not monitor:
            monitor = initialize_monitor()
            if not monitor:
                logging.error("Failed to initialize monitor")
                return
        
        # Send startup message
        startup_msg = f"🎓 <b>Мониторинг стартиран</b>\nПроверявам {len(WEBSITES)} училища за свободни места."
        monitor.send_telegram_message(startup_msg)
        
        # Initial check
        monitor.check_all_websites(WEBSITES)
        
        # Get check interval
        check_interval_minutes = int(os.getenv("CHECK_INTERVAL", 480))
        check_interval_seconds = check_interval_minutes * 60
        
        logging.info(f"Monitor will check every {check_interval_minutes} minutes")
        
        while True:
            try:
                time.sleep(check_interval_seconds)
                monitor.check_all_websites(WEBSITES)
            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
                
    except Exception as e:
        logging.error(f"Fatal error in monitoring loop: {e}")

# Self-ping to prevent sleeping
def self_ping():
    while True:
        try:
            time.sleep(840)  # 14 minutes
            port = os.environ.get("PORT", 5000)
            # Try to get the external URL from Render environment
            external_url = os.environ.get("RENDER_EXTERNAL_URL")
            if external_url:
                ping_url = f"{external_url}/ping"
            else:
                ping_url = f"http://localhost:{port}/ping"
            
            response = requests.get(ping_url, timeout=10)
            logging.info(f"Self-ping successful: {response.status_code}")
        except Exception as e:
            logging.error(f"Self-ping failed: {e}")

# Flask routes
@app.route('/')
def home():
    return """
    <h1>🎓 School Monitor Service</h1>
    <p>✅ Service is running and monitoring school websites for available spots.</p>
    <p><a href="/status">Check Status</a> | <a href="/health">Health Check</a> | <a href="/check-now">Manual Check</a></p>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'school-monitor',
        'monitor_initialized': monitor is not None
    })

@app.route('/status')
def status():
    if monitor:
        return jsonify(monitor.get_status())
    return jsonify({
        'status': 'initializing',
        'message': 'Monitor is starting up...',
        'env_vars': {
            'bot_token_set': bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            'chat_id_set': bool(os.getenv("TELEGRAM_CHAT_ID")),
            'check_interval': os.getenv("CHECK_INTERVAL", 480)
        }
    })

@app.route('/check-now')
def check_now():
    """Manual trigger for checking websites"""
    global monitor
    if monitor:
        try:
            successful = monitor.check_all_websites(WEBSITES)
            return jsonify({
                'status': 'completed',
                'successful_checks': successful,
                'total_sites': len(WEBSITES),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    else:
        # Try to initialize monitor if it doesn't exist
        monitor = initialize_monitor()
        if monitor:
            successful = monitor.check_all_websites(WEBSITES)
            return jsonify({
                'status': 'completed',
                'successful_checks': successful,
                'total_sites': len(WEBSITES),
                'timestamp': datetime.now().isoformat(),
                'note': 'Monitor was initialized during this request'
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Monitor not initialized. Check environment variables.'
            }), 503

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == "__main__":
    try:
        logging.info("Starting Flask application...")
        
        # Initialize monitor in main thread first
        monitor = initialize_monitor()
        
        # Start the monitoring thread
        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
        logging.info("Monitor thread started")
        
        # Start self-ping thread
        ping_thread = threading.Thread(target=self_ping, daemon=True)
        ping_thread.start()
        logging.info("Self-ping thread started")
        
        # Start Flask app
        port = int(os.environ.get("PORT", 5000))
        logging.info(f"Starting Flask on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        raise
