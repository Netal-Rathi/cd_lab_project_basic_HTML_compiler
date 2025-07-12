from flask import Flask, render_template, request, jsonify, send_file
import webbrowser
import os
from datetime import datetime

app = Flask(__name__)

def tokenize_html(html):
    """Convert HTML string into tokens"""
    tokens = []
    pos = 0
    while pos < len(html):
        if html[pos] == "<":  
            end_pos = html.find(">", pos)
            if end_pos == -1:
                break
            tokens.append(html[pos:end_pos + 1])
            pos = end_pos + 1
        else:
            end_pos = html.find("<", pos)
            if end_pos == -1:
                end_pos = len(html)
            text = html[pos:end_pos].strip()
            if text:
                tokens.append(text)
            pos = end_pos
    return tokens

def is_opening_tag(token):
    """Check if token is an opening tag"""
    return token.startswith("<") and not token.startswith("</") and not token.endswith("/>")

def is_closing_tag(token):
    """Check if token is a closing tag"""
    return token.startswith("</")

def get_tag_name(token):
    """Extract tag name from token"""
    return token.strip("<>/").split()[0]

def parse_html(tokens):
    """Validate HTML structure and detect errors"""
    stack = []
    errors = []

    valid_parent_child = {
        "html": ["head", "body"],
        "head": ["title", "meta", "link", "style", "script"],
        "body": ["h1", "h2", "h3", "p", "div", "span", "table", "ul", "ol", "img", "br", "a", "footer", "header", "nav", "section", "article", "aside", "main"],
        "table": ["tr"],
        "tr": ["td", "th"],
        "ul": ["li"],
        "ol": ["li"],
        "p": ["b", "i", "strong", "em", "span", "a", "img", "br"],
        "div": ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "span", "a", "img", "footer", "section", "article", "header"],
        "section": ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "div"],
        "article": ["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "footer", "header", "section"],
        "nav": ["a", "ul", "ol"],
        "footer": ["p", "a", "ul", "ol"],
        "header": ["h1", "h2", "h3", "h4", "h5", "h6", "nav", "p"],
        "form": ["input", "select", "textarea", "button", "label", "fieldset", "legend"],
        "input": [],
        "textarea": [],
        "select": ["option"],
        "option": [],
        "label": ["input", "select", "textarea"],
        "button": ["input", "select", "textarea"]
    }

    self_closing_tags = {
        "br", "img", "meta", "link", "input", "hr", "base", "area", "col", "source", "track", "wbr"
    }

    for token in tokens:
        if is_opening_tag(token):
            tag_name = get_tag_name(token)
            if tag_name in self_closing_tags:
                continue  
            if stack:
                parent_tag = get_tag_name(stack[-1])
                if parent_tag in valid_parent_child and tag_name not in valid_parent_child[parent_tag]:
                    errors.append(f"Invalid nesting: <{tag_name}> inside <{parent_tag}>")
            stack.append(token)
        elif is_closing_tag(token):
            tag_name = get_tag_name(token)
            if not stack:
                errors.append(f"Unmatched closing tag: {token}")
            else:
                last_open = stack[-1]
                if get_tag_name(last_open) == tag_name:
                    stack.pop()
                else:
                    errors.append(f"Mismatched tag: Expected </{get_tag_name(last_open)}>, found {token}")
    
    while stack:
        errors.append(f"Unclosed tag: {stack.pop()}")

    return errors

def correct_html(tokens):
    """Correct HTML errors automatically"""
    stack = []
    corrected_tokens = []
    self_closing_tags = {"br", "img", "meta", "link", "input"}

    for token in tokens:
        if is_opening_tag(token):
            tag_name = get_tag_name(token)
            if tag_name not in self_closing_tags:
                stack.append(token)
            corrected_tokens.append(token)
        elif is_closing_tag(token):
            tag_name = get_tag_name(token)
            if stack and get_tag_name(stack[-1]) == tag_name:
                stack.pop()
                corrected_tokens.append(token)
            else:
                while stack and get_tag_name(stack[-1]) != tag_name:
                    corrected_tokens.append(f"</{get_tag_name(stack.pop())}>")
                if stack:
                    stack.pop()
                    corrected_tokens.append(token)
        else:
            corrected_tokens.append(token)

    while stack:
        corrected_tokens.append(f"</{get_tag_name(stack.pop())}>")

    return corrected_tokens

def save_html_file(corrected_html, filename=None):
    """Save corrected HTML to a file"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"corrected_output_{timestamp}.html"
    
    with open(filename, "w", encoding="utf-8") as file:
        file.write(corrected_html)
    
    return filename

@app.route('/')
def index():
    """Main page with HTML compiler interface"""
    return render_template('index.html')

@app.route('/compile', methods=['POST'])
def compile_html():
    """API endpoint to compile HTML"""
    try:
        html_code = request.json.get('html_code', '')
        
        if not html_code.strip():
            return jsonify({
                'success': False,
                'error': 'No HTML code provided'
            })
        
        # Tokenize HTML
        tokens = tokenize_html(html_code)
        
        # Parse and detect errors
        errors = parse_html(tokens)
        
        # Correct HTML
        corrected_tokens = correct_html(tokens)
        corrected_html = "<!DOCTYPE html>\n" + "\n".join(corrected_tokens)
        
        # Save corrected HTML
        filename = save_html_file(corrected_html)
        
        return jsonify({
            'success': True,
            'original_html': html_code,
            'corrected_html': corrected_html,
            'errors': errors,
            'error_count': len(errors),
            'filename': filename,
            'preview_url': f'/preview/{filename}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/preview/<filename>')
def preview_html(filename):
    """Preview the corrected HTML file"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            html_content = file.read()
        return html_content
    except FileNotFoundError:
        return "File not found", 404

@app.route('/download/<filename>')
def download_html(filename):
    """Download the corrected HTML file"""
    try:
        return send_file(filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found", 404

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create the HTML template
    template_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTML Compiler - Web Interface</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .content {
            padding: 30px;
        }
        
        .input-section {
            margin-bottom: 30px;
        }
        
        .input-section h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 1.5rem;
        }
        
        textarea {
            width: 100%;
            height: 200px;
            padding: 15px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: vertical;
            transition: border-color 0.3s ease;
        }
        
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .button-group {
            margin-top: 20px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }
        
        .btn-success {
            background: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        
        .results-section {
            margin-top: 30px;
        }
        
        .error-count {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #dc3545;
        }
        
        .error-list {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .error-item {
            color: #856404;
            margin-bottom: 8px;
            padding-left: 20px;
            position: relative;
        }
        
        .error-item:before {
            content: "⚠️";
            position: absolute;
            left: 0;
        }
        
        .output-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .output-section h3 {
            color: #333;
            margin-bottom: 15px;
        }
        
        .code-block {
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            overflow-x: auto;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .hidden {
            display: none;
        }
        
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #28a745;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 10px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .content {
                padding: 20px;
            }
            
            .button-group {
                flex-direction: column;
            }
            
            .btn {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛠️ HTML Compiler</h1>
            <p>Parse, validate, and correct HTML code with error detection</p>
        </div>
        
        <div class="content">
            <div class="input-section">
                <h2>📝 Input HTML Code</h2>
                <textarea id="htmlInput" placeholder="Enter your HTML code here...&#10;&#10;Example:&#10;&lt;html&gt;&#10;&lt;head&gt;&#10;&lt;title&gt;My Page&lt;/title&gt;&#10;&lt;/head&gt;&#10;&lt;body&gt;&#10;&lt;h1&gt;Welcome&lt;/h1&gt;&#10;&lt;p&gt;This is a test&lt;/p&gt;&#10;&lt;/body&gt;&#10;&lt;/html&gt;"></textarea>
                
                <div class="button-group">
                    <button class="btn btn-primary" onclick="compileHTML()">🔧 Compile & Correct</button>
                    <button class="btn btn-secondary" onclick="clearInput()">🗑️ Clear</button>
                    <button class="btn btn-secondary" onclick="loadExample()">📋 Load Example</button>
                </div>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Processing HTML code...</p>
            </div>
            
            <div class="results-section hidden" id="results">
                <div class="success-message" id="successMessage"></div>
                
                <div class="error-count hidden" id="errorCount"></div>
                
                <div class="error-list hidden" id="errorList"></div>
                
                <div class="output-section">
                    <h3>✅ Corrected HTML Output</h3>
                    <div class="code-block" id="correctedOutput"></div>
                    
                    <div class="button-group" style="margin-top: 20px;">
                        <button class="btn btn-success" onclick="previewHTML()">👁️ Preview</button>
                        <button class="btn btn-primary" onclick="downloadHTML()">📥 Download</button>
                        <button class="btn btn-secondary" onclick="copyToClipboard()">📋 Copy</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentResult = null;
        
        function compileHTML() {
            const htmlInput = document.getElementById('htmlInput').value.trim();
            
            if (!htmlInput) {
                alert('Please enter some HTML code first!');
                return;
            }
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').classList.add('hidden');
            
            // Make API call
            fetch('/compile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    html_code: htmlInput
                })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                
                if (data.success) {
                    currentResult = data;
                    displayResults(data);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                document.getElementById('loading').style.display = 'none';
                alert('Error: ' + error.message);
            });
        }
        
        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            const successMessage = document.getElementById('successMessage');
            const errorCount = document.getElementById('errorCount');
            const errorList = document.getElementById('errorList');
            const correctedOutput = document.getElementById('correctedOutput');
            
            // Show results section
            resultsDiv.classList.remove('hidden');
            
            // Display success message
            if (data.error_count === 0) {
                successMessage.innerHTML = '🎉 No errors found! HTML is valid.';
                errorCount.classList.add('hidden');
                errorList.classList.add('hidden');
            } else {
                successMessage.innerHTML = `🔧 HTML compiled successfully! ${data.error_count} error(s) detected and corrected.`;
                errorCount.classList.remove('hidden');
                errorCount.innerHTML = `Found ${data.error_count} error(s):`;
                
                errorList.classList.remove('hidden');
                errorList.innerHTML = '';
                data.errors.forEach(error => {
                    const errorItem = document.createElement('div');
                    errorItem.className = 'error-item';
                    errorItem.textContent = error;
                    errorList.appendChild(errorItem);
                });
            }
            
            // Display corrected HTML
            correctedOutput.textContent = data.corrected_html;
        }
        
        function clearInput() {
            document.getElementById('htmlInput').value = '';
            document.getElementById('results').classList.add('hidden');
        }
        
        function loadExample() {
            const exampleHTML = `<html>
<head>
<title>Test Page
<body>
<h1>Hello World
<p>This is a paragraph with <strong>bold text</strong>
<ul>
<li>Item 1
<li>Item 2
</ul>
</html>`;
            
            document.getElementById('htmlInput').value = exampleHTML;
        }
        
        function previewHTML() {
            if (currentResult && currentResult.filename) {
                window.open(`/preview/${currentResult.filename}`, '_blank');
            }
        }
        
        function downloadHTML() {
            if (currentResult && currentResult.filename) {
                window.open(`/download/${currentResult.filename}`, '_blank');
            }
        }
        
        function copyToClipboard() {
            if (currentResult) {
                navigator.clipboard.writeText(currentResult.corrected_html).then(() => {
                    alert('Corrected HTML copied to clipboard!');
                }).catch(() => {
                    alert('Failed to copy to clipboard. Please copy manually.');
                });
            }
        }
        
        // Add keyboard shortcut (Ctrl+Enter to compile)
        document.getElementById('htmlInput').addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                compileHTML();
            }
        });
    </script>
</body>
</html>'''
    
    # Write the template file
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(template_html)
    
    print("🚀 HTML Compiler Web Interface")
    print("=" * 40)
    print("📋 Project: HTML Compiler with Web Frontend")
    print("👥 Team: Hariom Nabira (34) & Harsh Tiwari (37)")
    print("📚 Course: Compiler Design Lab")
    print("=" * 40)
    print("🌐 Starting web server...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 40)
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000) 