# ... (Keep your existing imports, BeautifulSoup, and YouTube functions the same)

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

    # Initialize protocol modifiers
    protocol_security = "Secure Connection (HTTPS)"
    protocol_score_modifier = 0

    # ⚠️ NEW: Check for lack of SSL/HTTPS encryption
    if protocol == "http":
        protocol_security = "Unencrypted Connection (HTTP - Not Secure)"
        protocol_score_modifier = -25  # Dock points for missing SSL

    # Basic Blacklist Check
    domain_status = "Checked Source"
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

    # Fallback if scraping fails
    if not extracted_content:
        # Calculate a basic score using the new protocol modifier
        fallback_score = max(10, 80 + domain_score_modifier + protocol_score_modifier)
        return jsonify({
            'trust_score': f"{fallback_score}%",
            'sensationalism': "Unknown (Could not read content)",
            'domain_authority': f"{domain_status} | {protocol_security}",
            'verdict': "Warning: Connection not secure" if protocol == "http" else "Unverified"
        })

    # 🧠 ENGINE 3: Deep Content AI Analysis
    ai_raw_output = analyze_content_with_ai(extracted_content, content_type)
    
    # Parse the response safely
    trust_score = 50
    sensationalism = "Medium"
    verdict = "Unverified"
    summary_reason = "Checked by AI"
    
    if ai_raw_output:
        lines = ai_raw_output.strip().split('\n')
        for line in lines:
            if line.startswith("Trust Score:"):
                try:
                    # Extract the raw numeric score from the AI response
                    trust_score = int(''.join(filter(str.isdigit, line)))
                except:
                    trust_score = 50
            elif line.startswith("Sensationalism:"):
                sensationalism = line.replace('Sensationalism:', '').strip()
            elif line.startswith("Safety Verdict:"):
                verdict = line.replace('Safety Verdict:', '').strip()
            elif line.startswith("Summary Reason:"):
                summary_reason = line.replace('Summary Reason:', '').strip()

    # Apply the protocol security penalty to the final AI trust score
    final_trust_score = max(10, trust_score + protocol_score_modifier)
    
    # Override verdict if connection is dangerous/unencrypted
    if protocol == "http" and verdict == "Safe to open":
        verdict = "Insecure Connection (Proceed with Caution)"

    return jsonify({
        'trust_score': f"{final_trust_score}%",
        'sensationalism': sensationalism,
        'domain_authority': f"{content_type} ({domain})",
        'connection_security': protocol_security,
        'verdict': verdict,
        'reason': summary_reason
    })
