from flask import Flask, request, jsonify
from flask_cors import CORS
from textblob import TextBlob
import urllib.parse

app = Flask(__name__)
CORS(app)  # Enables cross-origin requests so your HTML files can talk to Flask

# A simple mock blacklist for Engine 1 (URL analysis)
KNOW_FAKE_DOMAINS = ["fakenews.co", "theonion-clone.xyz", "dailyrumor.info", "baddata.net"]

@app.route('/api/analyze', methods=['POST'])
def analyze_article():
    data = request.json
    url = data.get('url', '')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # 🌐 ENGINE 1: URL & Domain Analysis
    try:
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.lower().replace('www.', '')
    except Exception:
        domain = ""

    # Simple logic checks
    domain_verified = "Verified Source"
    domain_score_modifier = 0

    if domain in KNOW_FAKE_DOMAINS:
        domain_verified = "Flagged Fake Source"
        domain_score_modifier = -50
    elif any(domain.endswith(ext) for ext in ['.xyz', '.top', '.info', '.click']):
        domain_verified = "Untrusted Extension"
        domain_score_modifier = -20

    # 🧠 ENGINE 2: Linguistic & NLP Bias Analysis
    # For testing, we extract text from the path, or simulate an article headline
    headline_text = parsed_url.path.replace('-', ' ').replace('/', ' ')
    if not headline_text.strip():
        headline_text = "Breaking sensational news discovery shocks the community completely"

    blob = TextBlob(headline_text)
    
    # TextBlob Subjectivity ranges from 0.0 (highly objective) to 1.0 (highly opinionated/biased)
    subjectivity = blob.sentiment.subjectivity 
    
    # Calculate a custom Clickbait rating based on subjectivity metrics
    if subjectivity > 0.6:
        sensationalism_rating = "High"
        nlp_score_modifier = -30
    elif subjectivity > 0.3:
        sensationalism_rating = "Medium"
        nlp_score_modifier = -10
    else:
        sensationalism_rating = "Low"
        nlp_score_modifier = 0

    # Calculate overall Trust Score (Starting at 95% down to minimum 10%)
    final_trust_score = max(10, 95 + domain_score_modifier + nlp_score_modifier)

    # Respond back to our HTML Dashboard page
    return jsonify({
        'trust_score': f"{final_trust_score}%",
        'sensationalism': sensationalism_rating,
        'domain_authority': domain_verified
    })

if __name__ == '__main__':
    # Runs the backend server on http://127.0.0.1:5000
    app.run(debug=True, port=5000)