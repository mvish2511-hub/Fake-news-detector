from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
# Enable CORS so your local HTML frontend can make requests to this backend securely
CORS(app)

# Predefined risk vectors
KNOW_FAKE_DOMAINS = ['fakenews.co', 'dailyrumor.info', 'onion-clone.xyz', 'rumorleak.net']
CLICKBAIT_TOKENS = ['shocking', 'outrageous', 'secret', 'miracle', 'shocks', 'breaking', 'unbelievable', 'won\'t believe']

def extract_article_content(url):
    """
    Attempts to download the web page and scrape paragraph elements to inspect real content body text.
    """
    try:
        # Pass a standard browser User-Agent header to avoid being blocked by anti-scraping firewalls
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pull text inside all paragraph tags (<p>)
        paragraphs = soup.find_all('p')
        full_text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
        
        return full_text if len(full_text) > 50 else None
    except Exception:
        return None

@app.route('/api/analyze',申明=['POST'])
@app.route('/api/analyze', methods=['POST'])
def analyze_link():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL parameter found in payload'}), 400

    target_url = data['url'].strip()
    
    # 1. Base Default Configurations
    trust_score = 95
    sensationalism = "Low"
    domain_authority = "Verified Source"
    
    # Isolate Domain Registry Metrics
    try:
        parsed_url = urllib.parse.urlparse(target_url)
        domain = parsed_url.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
    except Exception:
        return jsonify({'error': 'Invalid layout configuration of string address'}), 400

    # 2. Vector A: Domain Name Audit Vetting
    # Check explicitly flagged lists
    if any(fake in domain for fake in KNOW_FAKE_DOMAINS):
        trust_score -= 50
        domain_authority = "Flagged Source System"
    # Check suspicious unmonitored cheap TLD extensions
    elif domain.endswith(('.xyz', '.top', '.click', '.info', '.biz', '.live')):
        trust_score -= 25
        domain_authority = "Untrusted Domain"

    # 3. Vector B: Text Analysis (URL Path Token Verification)
    url_path_lower = parsed_url.path.lower()
    url_matches = 0
    for token in CLICKBAIT_TOKENS:
        if token in url_path_lower:
            url_matches += 1

    # 4. Vector C: Real Deep Scrape Content Verification
    scraped_body_text = extract_article_content(target_url)
    body_matches = 0
    
    if scraped_body_text:
        body_text_lower = scraped_body_text.lower()
        # Look for clickbait phrases inside the actual article text copy
        for token in CLICKBAIT_TOKENS:
            # Use regex boundaries to find whole standalone words
            matches = re.findall(r'\b' + re.escape(token) + r'\b', body_text_lower)
            if len(matches) > 0:
                body_matches += 1
                
        # If the text body content is completely empty or incredibly short, flag as suspicious structure
        if len(scraped_body_text) < 150:
            trust_score -= 15
    else:
        # Penalize slightly if the site blocks connections completely or has zero text readability
        trust_score -= 10

    # 5. Compile Cumulative Performance Math Rules
    total_flags = url_matches + body_matches
    
    if total_flags >= 4:
        sensationalism = "High Clickbait"
        trust_score -= 40
    elif total_flags >= 2:
        sensationalism = "Medium Bias"
        trust_score -= 20
    elif total_flags == 1:
        sensationalism = "Minor Bias"
        trust_score -= 5

    # Enforce standard ceiling/floor safety constraints
    if trust_score > 95: trust_score = 95
    if trust_score < 10: trust_score = 10

    # 6. Deliver Unified Structural Telemetry Object back to JavaScript
    return jsonify({
        'url': target_url,
        'domain': domain,
        'trust_score': f"{trust_score}%",
        'sensationalism': sensationalism,
        'domain_authority': domain_authority,
        'scraped_characters': len(scraped_body_text) if scraped_body_text else 0
    })

if __name__ == '__main__':
    print("🚀 VeriMedia Live Analytical Scraper Online...")
    app.run(port=5000, debug=True)
