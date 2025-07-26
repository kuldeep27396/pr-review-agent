#!/usr/bin/env node

const readline = require('readline');
const fs = require('fs');
const path = require('path');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

async function setupGitHubApp() {
  console.log('🚀 GitHub PR Review Agent Setup\n');
  
  console.log('First, create a GitHub App at: https://github.com/settings/apps/new');
  console.log('Use these settings:');
  console.log('Use these settings:');
  console.log('- App name: Your unique app name');
  console.log('- Homepage URL: Your deployment URL or GitHub repo');
  console.log('- Webhook URL: https://your-domain.com/webhook');
  console.log('- Webhook secret: Generate a secure random string');
  console.log('- Permissions:');
  console.log('  - Repository permissions:');
  console.log('    - Contents: Read');
  console.log('    - Pull requests: Write');
  console.log('    - Metadata: Read');
  console.log('- Subscribe to events:');
  console.log('  - Pull request');
  console.log('  - Pull request review\n');

  const appId = await question('Enter your GitHub App ID: ');
  const webhookSecret = await question('Enter your webhook secret: ');
  
  console.log('\nNow download the private key from your GitHub App settings page.');
  const privateKeyPath = await question('Enter the path to your private key file (.pem): ');
  
  let privateKey;
  try {
    privateKey = fs.readFileSync(privateKeyPath, 'utf8');
  } catch (error) {
    console.error('Error reading private key file:', error.message);
    process.exit(1);
  }

  const groqApiKey = await question('Enter your Groq API key (get one at https://console.groq.com/): ');

  const envContent = `# GitHub App Configuration
GITHUB_APP_ID=${appId}
GITHUB_PRIVATE_KEY="${privateKey.replace(/\n/g, '\\n')}"
GITHUB_WEBHOOK_SECRET=${webhookSecret}

# Groq API Configuration
GROQ_API_KEY=${groqApiKey}

# Server Configuration
PORT=3000
NODE_ENV=production

# Optional: Custom review settings
MAX_FILES_TO_REVIEW=10
MAX_FILE_SIZE_KB=100
REVIEW_TIMEOUT_MS=30000
LOG_LEVEL=info`;

  const envPath = path.join(process.cwd(), '.env');
  fs.writeFileSync(envPath, envContent);

  console.log('\n✅ Configuration saved to .env file');
  console.log('\nNext steps:');
  console.log('1. Install the GitHub App on your repositories');
  console.log('2. Deploy this application to your hosting service');
  console.log('3. Update your GitHub App webhook URL to point to your deployment');
  console.log('4. Test by creating a pull request in an installed repository');
  
  rl.close();
}

setupGitHubApp().catch(console.error);
