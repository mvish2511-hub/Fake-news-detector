from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
import os

app = Flask(__name__)
CORS(app)

# Initialize the Gemini Client 
# (Make sure to set your GEMINI_API_KEY environment variable)
client = genai.Client()

KNOW_FAKE_DOMAINS = ["fakenews.co", "theonion-clone.xyz", "dailyrumor.info", "baddata.net"]

def extract_youtube_transcript(video_url):
    """Extracts text transcript from a YouTube video URL."""
    try:
        parsed = urllib.parse.urlparse(video_url)
        # Handle both youtube.com/watch?v=... and youtu.be/...
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
        
        # Remove script and style elements so we only get readable text
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text = soup.get_text(separator=' ')
        # Clean up whitespace gaps
        cleaned_text = " ".join(text.split())
        return cleaned_text[:6000] # Limit characters to prevent massive token usage
    except Exception as e:
        print(f"Error scraping webpage: {e}")
        return None

def analyze_content_with_ai(content, content_type):
    """Uses Gemini to evaluate safety, truthfulness, and overall trust score."""
    prompt = f"""
    You are a pre-click security and fact-checking assistant. Analyze the following content extracted from a {content_type}.
    
    Content to evaluate:
    \"\"\"{content}\"\"\"
    
    Provide your evaluation strictly in the following format (do not add markdown code blocks or extra text, just the fields):
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

    # 🌐 ENGINE 1: URL & Domain Routing
    try:
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.lower().replace('www.', '')
    except Exception:
        return jsonify({'error': 'Invalid URL format'}), 400

    # Basic Blacklist Check remains as an instant fallback flag
    domain_status = "Checked Source"
    if domain in KNOW_FAKE_DOMAINS:
        domain_status = "Flagged Fake Source"

    # 📥 ENGINE 2: Dynamic Content Extraction
    extracted_content = None
    content_type = "webpage"

    if "youtube.com" in domain or "youtu.be" in domain:
        content_type = "YouTube Video"
        extracted_content = extract_youtube_transcript(url)
    else:
        content_type = "Standard Web Article"
        extracted_content = extract_webpage_text(url)

    # If extraction completely fails, fallback to handling just the domain/URL structure
    if not extracted_content:
        return jsonify({
            'trust_score': "30%" if domain_status == "Flagged Fake Source" else "50%",
            'sensationalism': "Unknown (Could not read content)",
            'domain_authority': domain_status,
            'verdict': "Warning: Content unreadable before clicking"
        })

    # 🧠 ENGINE 3: Deep Content AI Analysis
    ai_raw_output = analyze_content_with_ai(extracted_content, content_type)
    
    # Parse the response safely
    trust_score = "50%"
    sensationalism = "Medium"
    verdict = "Unverified"
    
    if ai_raw_output:
        lines = ai_raw_output.strip().split('\n')
        for line in lines:
            if line.startswith("Trust Score:"):
                trust_score = f"{line.replace('Trust Score:', '').strip()}%"
            elif line.startswith("Sensationalism:"):
                sensationalism = line.replace('Sensationalism:', '').strip()
            elif line.startswith("Safety Verdict:"):
                verdict = line.replace('Safety Verdict:', '').strip()
            elif line.startswith("Summary Reason:"):
                domain_status = line.replace('Summary Reason:', '').strip()

    return jsonify({
        'trust_score': trust_score,
        'sensationalism': sensationalism,
        'domain_authority': f"{content_type} ({domain})",
        'verdict': verdict,
        'reason': domain_status
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
