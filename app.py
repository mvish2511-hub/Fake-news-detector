from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
import os

app = Flask(__name__)
# Enables cross-origin requests so your GitHub Pages frontend can talk to localhost:5000
CORS(app)  

# Initialize the Gemini Client
# Make sure your GEMINI_API_KEY environment variable is set in your system terminal
client = genai.Client()

# Mock blacklist fallback
KNOW_FAKE_DOMAINS = ["fakenews.co", "theonion-clone.xyz", "dailyrumor.info", "baddata.net"]

def extract_youtube_transcript(video_url):
    """Extracts text transcript from a YouTube video URL."""
    try:
        parsed = urllib.parse.urlparse(video_url)
        if 'youtu.be' in parsed.netloc:
            video_id = parsed.path.strip('/')
        else:
            video_id = urllib.parse.parse_qs(parsed.query).get('v', [None])[0]
        
        if not video_id:
            return None
        
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([item['text'] for item in transcript_list])
        return transcript_text
    except Exception as e:
        print(f"Error fetching YT transcript: {e}")
        return None

def extract_webpage_text(url):
    """Scrapes the visible text content from a generic web page."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strip away code elements to leave only pure readable text
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text = soup.get_text(separator=' ')
        cleaned_text = " ".join(text.split())
        return cleaned_text[:6000]  # Hard cap to stay within reasonable token/processing boundaries
    except Exception as e:
        print(f"Error scraping webpage: {e}")
        return None

def analyze_content_with_ai(content, content_type):
    """Uses Gemini to evaluate safety, truthfulness, and overall trust score."""
    prompt = f"""
    You are a pre-click security and fact-checking assistant. Analyze the following content extracted from a {content_type}.
    
    Content to evaluate:
    \"\"\"{content}\"\"\"
    
    Provide your evaluation strictly in the following format (do not add markdown code blocks, bold symbols, or extra text, just return these lines):
    Trust Score: [Insert a number from 10 to 95 based on factual reliability and safety]
    Sensationalism: [Low, Medium, or High]
    Safety Verdict: [Safe to open, Misleading/Clickbait, Dangerous/Malicious, or Unverified/Fake]
    Summary Reason: [Provide a brief, 1-sentence reason for your score]
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return None

@app.route('/api/analyze', methods=['POST'])
def analyze_article():
    data = request.json
    url = data.get('url', '')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    # 🌐 ENGINE 1: URL, Domain & Protocol Analysis
    try:
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.lower().replace('www.', '')
        protocol = parsed_url.scheme.lower()  # Extracts 'http' or 'https'
    except Exception:
        return jsonify({'error': 'Invalid URL format'}), 400

    domain_status = "Verified Source"
    domain_score_modifier = 0

    if domain in KNOW_FAKE_DOMAINS:
        domain_status = "Flagged Fake Source"
        domain_score_modifier = -50
    elif any(domain.endswith(ext) for ext in ['.xyz', '.top', '.info', '.click']):
        domain_status = "Untrusted Extension"
        domain_score_modifier = -20

    # 📥 ENGINE 2: Dynamic Content Extraction
    extracted_content = None
    content_type = "webpage"

    if "youtube.com" in domain or "youtu.be" in domain:
        content_type = "YouTube Video"
        extracted_content = extract_youtube_transcript(url)
    else:
        content_type = "Standard Web Article"
        extracted_content = extract_webpage_text(url)

    # Fallback response structure if the scraper cannot bypass a firewall or access the site
    if not extracted_content:
        fallback_score = max(10, 85 + domain_score_modifier)
        if protocol == "http":
            fallback_score = 45  # Force a dangerous rating if unencrypted
            domain_status = "Insecure Connection (HTTP)"
        
        return jsonify({
            'trust_score': f"{fallback_score}%",
            'sensationalism': "Unknown (Unreadable Content)",
            'domain_authority': f"{domain_status}",
            'verdict': "Warning: Connection unsafe or unreadable before clicking"
        })

    # 🧠 ENGINE 3: Deep Content AI Analysis
    ai_raw_output = analyze_content_with_ai(extracted_content, content_type)
    
    # Defaults in case parsing encounters unexpected structures
    trust_score = 70
    sensationalism = "Medium"
    verdict = "Unverified"
    summary_reason = "Evaluated based on content analysis"
    
    if ai_raw_output:
        lines = ai_raw_output.strip().split('\n')
        for line in lines:
            if line.startswith("Trust Score:"):
                try:
                    trust_score = int(''.join(filter(str.isdigit, line)))
                except:
                    trust_score = 70
            elif line.startswith("Sensationalism:"):
                sensationalism = line.replace('Sensationalism:', '').strip()
            elif line.startswith("Safety Verdict:"):
                verdict = line.replace('Safety Verdict:', '').strip()
            elif line.startswith("Summary Reason:"):
                summary_reason = line.replace('Summary Reason:', '').strip()

    # ⚠️ PROTOCOL ENFORCEMENT OVERRIDE
    # If the domain is missing SSL (HTTP), we forcefully sabotage the trust metrics
    if protocol == "http":
        final_trust_score = 40  # Hard drop to immediately register visually on the chart
        domain_status = "UNENCRYPTED SOURCE (NOT SECURE)"
        verdict = "Insecure Connection"
    else:
        final_trust_score = max(10, trust_score + domain_score_modifier)

    return jsonify({
        'trust_score': f"{final_trust_score}%",
        'sensationalism': sensationalism,
        'domain_authority': f"{domain_status} ({domain})",
        'verdict': verdict,
        'reason': summary_reason
    })

if __name__ == '__main__':
    # Runs the local development microservice backend
    app.run(debug=True, port=5000)
