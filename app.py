from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

import urllib.parse
import requests
import os
import re

# -------------------------------------------------------
# Gemini API Key
# -------------------------------------------------------
# Paste your real key between the quotes below.
# Get one free at: https://aistudio.google.com/apikey

from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set.\n"
        "Open app.py and replace PASTE_YOUR_GEMINI_API_KEY_HERE "
        "with your actual Gemini API key."
    )

client = genai.Client(api_key=GEMINI_API_KEY)

# -------------------------------------------------------
# Flask App
# -------------------------------------------------------

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# -------------------------------------------------------
# Fake Domain Database
# -------------------------------------------------------

KNOWN_FAKE_DOMAINS = [
    "fakenews.co",
    "theonion-clone.xyz",
    "dailyrumor.info",
    "baddata.net"
]

# -------------------------------------------------------
# YouTube Transcript Extraction
# -------------------------------------------------------

def extract_youtube_transcript(video_url):
    try:

        parsed = urllib.parse.urlparse(video_url)

        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/")
        else:
            video_id = urllib.parse.parse_qs(
                parsed.query
            ).get("v", [None])[0]

        if not video_id:
            return None

        transcript = YouTubeTranscriptApi.get_transcript(video_id)

        return " ".join(
            item["text"]
            for item in transcript
        )

    except Exception as e:
        print("Transcript Error:", e)
        return None


# -------------------------------------------------------
# Website Scraper
# -------------------------------------------------------

def extract_webpage_text(url):

    try:

        headers = {
            "User-Agent":
            "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for tag in soup(
            [
                "script",
                "style",
                "header",
                "footer",
                "nav",
                "aside"
            ]
        ):
            tag.decompose()

        text = soup.get_text(" ")

        text = " ".join(text.split())

        return text[:6000]

    except Exception as e:
        print("Scraping Error:", e)
        return None


# -------------------------------------------------------
# Gemini Analysis
# -------------------------------------------------------

def analyze_content_with_ai(content, content_type):

    prompt = f"""
You are an AI Cyber Security Assistant.

Analyze this {content_type}.

Check for:

• Scam
• Fake news
• Clickbait
• Malware
• Phishing
• Dangerous content

Content:

{content}

Return ONLY:

Trust Score: 10-95
Sensationalism: Low/Medium/High
Safety Verdict: Safe to Open / Misleading / Dangerous / Fake
Summary Reason: one sentence only.
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        print("Gemini Error:", e)

        return None
# -------------------------------------------------------
# Main API
# -------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def analyze_article():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "No JSON received."
            }), 400

        url = data.get("url", "").strip()

        if url == "":
            return jsonify({
                "error": "No URL provided."
            }), 400

        # ----------------------------
        # Validate URL
        # ----------------------------

        if not (
            url.startswith("http://")
            or
            url.startswith("https://")
        ):
            return jsonify({
                "error": "URL must begin with http:// or https://"
            }), 400

        parsed = urllib.parse.urlparse(url)

        domain = parsed.netloc.lower().replace("www.", "")

        protocol = parsed.scheme.lower()

        # ----------------------------
        # Domain Reputation
        # ----------------------------

        domain_status = "Verified Domain"

        penalty = 0

        if domain in KNOWN_FAKE_DOMAINS:

            domain_status = "Known Fake Domain"

            penalty = -50

        elif any(
            domain.endswith(ext)
            for ext in [
                ".xyz",
                ".top",
                ".click",
                ".info"
            ]
        ):

            domain_status = "Suspicious Domain"

            penalty = -20

        # ----------------------------
        # Content Extraction
        # ----------------------------

        if (
            "youtube.com" in domain
            or
            "youtu.be" in domain
        ):

            content_type = "YouTube Video"

            content = extract_youtube_transcript(url)

        else:

            content_type = "Web Article"

            content = extract_webpage_text(url)

        # ----------------------------
        # Fallback if Extraction Fails
        # ----------------------------

        if not content:

            score = max(10, 85 + penalty)

            if protocol == "http":

                score = 40

                domain_status = "HTTP (Unencrypted)"

            return jsonify({

                "trust_score": f"{score}%",

                "sensationalism":
                "Unknown",

                "domain_authority":
                domain_status,

                "verdict":
                "Unable to Inspect",

                "reason":
                "Content could not be extracted."

            })

        # ----------------------------
        # AI Analysis
        # ----------------------------

        ai_output = analyze_content_with_ai(
            content,
            content_type
        )

        trust_score = 75

        sensationalism = "Medium"

        verdict = "Unverified"

        reason = "No AI response."

        if ai_output:

            trust = re.search(r"Trust Score:\s*\*?(\d+)", ai_output, re.I)
            sensational = re.search(r"Sensationalism:\s*\*?([a-zA-Z]+)", ai_output, re.I)
            verdict_match = re.search(r"Safety Verdict:\s*\*?([^\n\r]+)", ai_output, re.I)
            reason_match = re.search(r"Summary Reason:\s*\*?([^\n\r]+)", ai_output, re.I)

            if trust:
                trust_score = int(trust.group(1))

            if sensational:
                sensationalism = sensational.group(1).strip()

            if verdict_match:
                verdict = verdict_match.group(1).strip()

            if reason_match:
                reason = reason_match.group(1).strip()

        # ----------------------------
        # HTTP Override
        # ----------------------------

        if protocol == "http":

            trust_score = 40

            verdict = "Insecure Connection"

            domain_status = "UNENCRYPTED SOURCE (HTTP)"

            reason = (
                "Website is using HTTP instead of HTTPS. "
                + reason
            )

        else:

            trust_score = max(
                10,
                min(95, trust_score + penalty)
            )

            domain_status = (
                f"{domain_status} ({domain})"
            )

        # ----------------------------
        # Return Result
        # ----------------------------

        return jsonify({

            "trust_score":
            f"{trust_score}%",

            "sensationalism":
            sensationalism,

            "domain_authority":
            domain_status,

            "verdict":
            verdict,

            "reason":
            reason

        })

    except Exception as e:

        print("Backend Error:", e)

        return jsonify({

            "error": str(e)

        }), 500
# -------------------------------------------------------
# Health Check API
# -------------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "service": "VeriMedia AI Backend",
        "version": "1.0",
        "message": "Backend is running successfully."
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy"
    })


# -------------------------------------------------------
# Global Error Handlers
# -------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found."
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error."
    }), 500


# -------------------------------------------------------
# Run Flask
# -------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print(" VeriMedia Backend Started ")
    print("=" * 60)
    print("API Endpoint : http://127.0.0.1:5000/api/analyze")
    print("Health Check : http://127.0.0.1:5000/api/health")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
