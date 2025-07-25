const express = require('express');
const path = require('path');
const fs = require('fs');

// Mock environment for testing
process.env.GITHUB_APP_ID = 'test-app-id';
process.env.GITHUB_PRIVATE_KEY = 'test-private-key';
process.env.GITHUB_WEBHOOK_SECRET = 'test-webhook-secret';
process.env.GROQ_API_KEY = 'test-groq-key';
process.env.NODE_ENV = 'test';
process.env.PORT = '3001';

const app = express();
const port = 3001;

app.use(express.json());
app.use(express.static('public'));

// Mock endpoints to test the basic structure
app.get('/', (req, res) => {
  res.json({
    name: 'GitHub PR Review Agent - Test Mode',
    description: 'Automated PR reviews powered by Groq AI',
    status: 'running',
    mode: 'test',
    timestamp: new Date().toISOString()
  });
});

app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString(),
    mode: 'test'
  });
});

app.post('/webhook', (req, res) => {
  console.log('📩 Webhook received (test mode):');
  console.log('Headers:', req.headers);
  console.log('Body:', JSON.stringify(req.body, null, 2));
  
  res.json({ 
    received: true, 
    timestamp: new Date().toISOString(),
    note: 'Test mode - webhook received but not processed'
  });
});

// Test endpoint to simulate PR review
app.post('/test-review', (req, res) => {
  const mockPRData = {
    action: 'opened',
    pull_request: {
      number: 123,
      title: 'Add new feature',
      body: 'This PR adds a new awesome feature',
      html_url: 'https://github.com/test/repo/pull/123'
    },
    repository: {
      name: 'test-repo',
      owner: { login: 'test-user' }
    }
  };

  console.log('🔍 Simulating PR review for:', mockPRData.pull_request.title);
  
  res.json({
    message: 'PR review simulation completed',
    pr: mockPRData.pull_request,
    note: 'In production, this would trigger AI analysis via Groq'
  });
});

// Serve a simple test page
app.get('/test', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub PR Review Agent - Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .test-section { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 5px; }
            .button { background: #0366d6; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
            .button:hover { background: #0256cc; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 GitHub PR Review Agent</h1>
                <p>Test Interface - Local Development</p>
            </div>
            
            <div class="test-section">
                <h3>📊 Service Status</h3>
                <div class="status success">✅ Server is running on port ${port}</div>
                <div class="status info">ℹ️ Running in test mode with mock data</div>
            </div>
            
            <div class="test-section">
                <h3>🧪 Test Endpoints</h3>
                <button class="button" onclick="testEndpoint('/')">Test Home</button>
                <button class="button" onclick="testEndpoint('/health')">Test Health</button>
                <button class="button" onclick="testEndpoint('/test-review', 'POST')">Test PR Review</button>
                <div id="test-results" style="margin-top: 15px;"></div>
            </div>
            
            <div class="test-section">
                <h3>📋 Next Steps for Production</h3>
                <ol>
                    <li>Create a GitHub App at <a href="https://github.com/settings/apps/new" target="_blank">GitHub Apps</a></li>
                    <li>Get a Groq API key from <a href="https://console.groq.com/" target="_blank">Groq Console</a></li>
                    <li>Run the setup script: <code>node scripts/setup-github-app.js</code></li>
                    <li>Deploy to your preferred hosting platform</li>
                </ol>
            </div>
            
            <div class="test-section">
                <h3>🔧 Configuration</h3>
                <p>To run with real GitHub integration:</p>
                <pre style="background: #f1f1f1; padding: 15px; border-radius: 5px; overflow-x: auto;">
# Copy and configure environment variables
cp .env.example .env

# Run the setup wizard
node scripts/setup-github-app.js

# Start the production server
npm start</pre>
            </div>
        </div>
        
        <script>
            async function testEndpoint(endpoint, method = 'GET') {
                const resultsDiv = document.getElementById('test-results');
                resultsDiv.innerHTML = '<div class="status info">Testing ' + endpoint + '...</div>';
                
                try {
                    const response = await fetch(endpoint, { 
                        method: method,
                        headers: method === 'POST' ? { 'Content-Type': 'application/json' } : {}
                    });
                    const data = await response.json();
                    
                    resultsDiv.innerHTML = 
                        '<div class="status success">✅ ' + endpoint + ' - Status: ' + response.status + '</div>' +
                        '<pre style="background: #f1f1f1; padding: 10px; border-radius: 3px; margin: 10px 0; overflow-x: auto;">' + 
                        JSON.stringify(data, null, 2) + 
                        '</pre>';
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="status" style="background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;">❌ Error: ' + error.message + '</div>';
                }
            }
        </script>
    </body>
    </html>
  `);
});

app.listen(port, () => {
  console.log('\n🚀 GitHub PR Review Agent - Test Server');
  console.log('==========================================');
  console.log(`📍 Local server: http://localhost:${port}`);
  console.log(`🧪 Test interface: http://localhost:${port}/test`);
  console.log(`💊 Health check: http://localhost:${port}/health`);
  console.log('==========================================');
  console.log('📝 Running in TEST MODE with mock data');
  console.log('🔧 For production setup, run: node scripts/setup-github-app.js');
  console.log('==========================================\n');
});

process.on('SIGINT', () => {
  console.log('\n👋 Shutting down test server...');
  process.exit(0);
});