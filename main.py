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
        self.status = "Ready"
        self.is_checking = False
        logging.info("WebsiteMonitor initialized")
        
    def get_page_content(self, url, selector=None):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            # Reduced timeout to prevent hanging
            response = requests.get(url, headers=headers, timeout=8)
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
            response = requests.post(url, data=data, timeout=5)
            response.raise_for_status()
            logging.info("Telegram message sent")
            return True
        except Exception as e:
            logging.error(f"Telegram error: {e}")
            return False

    def check_website(self, url, name, selector=None):
        try:
            logging.info(f"Checking {name}")
            current_content = self.get_page_content(url, selector)
            if not current_content:
                return False

            current_hash = self.get_content_hash(current_content)
            previous_hash = self.previous_states.get(url)

            if not previous_hash:
                self.previous_states[url] = current_hash
                logging.info(f"{name}: baseline set")
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
        except Exception as e:
            logging.error(f"Error checking {name}: {e}")
            return False

    def check_all_websites(self, websites, max_time=120):
        """Check all websites with timeout protection"""
        if self.is_checking:
            logging.warning("Check already in progress, skipping...")
            return 0
            
        self.is_checking = True
        self.status = "Checking websites..."
        start_time = time.time()
        
        try:
            logging.info("=== Starting check cycle ===")
            successful_checks = 0
            
            for i, site in enumerate(websites):
                # Check if we're taking too long
                if time.time() - start_time > max_time:
                    logging.warning(f"Check timeout reached, stopping at site {i+1}/{len(websites)}")
                    break
                    
                try:
                    if self.check_website(site['url'], site['name'], site.get('selector')):
                        successful_checks += 1
                    time.sleep(1)  # Short delay between checks
                except Exception as e:
                    logging.error(f"Error checking {site['name']}: {e}")
            
            self.last_check = datetime.now()
            self.check_count += 1
            self.status = f"Active - Last: {self.last_check.strftime('%H:%M:%S')}"
            
            logging.info(f"=== Check complete: {successful_checks}/{len(websites)} successful ===")
            return successful_checks
            
        finally:
            self.is_checking = False

    def get_status(self):
        return {
            'status': self.status,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'check_count': self.check_count,
            'monitored_sites': len(WEBSITES),
            'is_checking': self.is_checking
        }

# Websites list (reduced for testing)
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
    }
]

# Global monitor instance
monitor = None

def initialize_monitor():
    """Initialize monitor with timeout protection"""
    global monitor
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logging.error("Missing environment variables")
            return None
            
        monitor = WebsiteMonitor(bot_token, chat_id)
        logging.info("Monitor initialized successfully")
        return monitor
    except Exception as e:
        logging.error(f"Error initializing monitor: {e}")
        return None

def background_monitoring():
    """Background monitoring with error recovery"""
    global monitor
    try:
        if not monitor:
            monitor = initialize_monitor()
            if not monitor:
                logging.error("Failed to initialize monitor")
                return
        
        # Send startup message
        startup_msg = f"🎓 Мониторинг стартиран за {len(WEBSITES)} училища"
        monitor.send_telegram_message(startup_msg)
        
        # Get check interval
        check_interval_minutes = int(os.getenv("CHECK_INTERVAL", 480))
        check_interval_seconds = check_interval_minutes * 60
        
        logging.info(f"Background monitoring every {check_interval_minutes} minutes")
        
        while True:
            try:
                monitor.check_all_websites(WEBSITES)
                time.sleep(check_interval_seconds)
            except Exception as e:
                logging.error(f"Error in background monitoring: {e}")
                time.sleep(300)  # Wait 5 minutes on error
                
    except Exception as e:
        logging.error(f"Fatal error in background monitoring: {e}")

def keep_alive():
    """Self-ping to prevent sleeping"""
    while True:
        try:
            time.sleep(840)  # 14 minutes
            external_url = os.environ.get("RENDER_EXTERNAL_URL")
            if external_url:
                requests.get(f"{external_url}/ping", timeout=5)
                logging.info("Keep-alive ping sent")
        except Exception as e:
            logging.error(f"Keep-alive failed: {e}")

# Flask routes
@app.route('/')
def home():
    return """
    <h1>🎓 School Monitor</h1>
    <p>✅ Service is running</p>
    <p><a href="/status">Status</a> | <a href="/health">Health</a> | <a href="/quick-check">Quick Check</a></p>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'monitor_ready': monitor is not None
    })

@app.route('/status')
def status():
    if monitor:
        return jsonify(monitor.get_status())
    return jsonify({
        'status': 'initializing',
        'env_vars': {
            'bot_token_set': bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            'chat_id_set': bool(os.getenv("TELEGRAM_CHAT_ID"))
        }
    })

@app.route('/quick-check')
def quick_check():
    """Quick check of just 2 sites to avoid timeout"""
    global monitor
    if not monitor:
        monitor = initialize_monitor()
        if not monitor:
            return jsonify({'error': 'Monitor not initialized'}), 500
    
    try:
        # Check only first 2 sites for speed
        quick_sites = WEBSITES[:2]
        successful = monitor.check_all_websites(quick_sites, max_time=30)
        
        return jsonify({
            'status': 'completed',
            'successful_checks': successful,
            'sites_checked': len(quick_sites),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/full-check')
def full_check():
    """Full check - use with caution, may timeout"""
    global monitor
    if not monitor:
        monitor = initialize_monitor()
        if not monitor:
            return jsonify({'error': 'Monitor not initialized'}), 500
    
    try:
        successful = monitor.check_all_websites(WEBSITES, max_time=90)
        return jsonify({
            'status': 'completed',
            'successful_checks': successful,
            'total_sites': len(WEBSITES),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == "__main__":
    try:
        logging.info("Starting application...")
        
        # Initialize monitor
        monitor = initialize_monitor()
        
        # Start background threads
        if monitor:
            bg_thread = threading.Thread(target=background_monitoring, daemon=True)
            bg_thread.start()
            logging.info("Background monitoring started")
        
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logging.info("Keep-alive started")
        
        # Start Flask
        port = int(os.environ.get("PORT", 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
        
    except Exception as e:
        logging.error(f"Startup failed: {e}")
        raise
