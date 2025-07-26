#!/usr/bin/env node

// Test GitHub authentication locally
require('dotenv').config();
const { createAppAuth } = require('@octokit/auth-app');

async function testGitHubAuth() {
  console.log('🧪 Testing GitHub App Authentication\n');

  const appId = process.env.GITHUB_APP_ID || '1666280';
  const privateKey = process.env.GITHUB_PRIVATE_KEY;
  const installationId = '77616266';

  console.log(`App ID: ${appId}`);
  console.log(`Private Key length: ${privateKey ? privateKey.length : 'MISSING'}`);
  console.log(`Private Key starts with: ${privateKey ? privateKey.substring(0, 50) + '...' : 'MISSING'}`);
  console.log(`Installation ID: ${installationId}\n`);

  if (!privateKey) {
    console.error('❌ GITHUB_PRIVATE_KEY environment variable not set');
    console.log('Set it with: export GITHUB_PRIVATE_KEY="$(cat your-private-key.pem)"');
    return;
  }

  try {
    console.log('🔑 Creating GitHub App auth...');
    const auth = createAppAuth({
      appId: parseInt(appId),
      privateKey: privateKey.replace(/\\n/g, '\n'),
      installationId: installationId,
    });

    console.log('✅ Auth object created successfully');

    console.log('🔍 Getting installation token...');
    const { token } = await auth({ type: 'installation' });
    console.log(`✅ Installation token obtained: ${token.substring(0, 20)}...`);

    console.log('\n🎉 GitHub authentication test PASSED!');
    console.log('Your credentials are working correctly.');

  } catch (error) {
    console.error('\n❌ GitHub authentication test FAILED:');
    console.error('Error:', error.message);
    
    if (error.message.includes('PEM')) {
      console.log('\n💡 Private Key Issues:');
      console.log('- Make sure you copied the entire .pem file content');
      console.log('- Include -----BEGIN RSA PRIVATE KEY----- and -----END RSA PRIVATE KEY-----');
      console.log('- Check for proper line breaks');
    }
    
    if (error.message.includes('App ID')) {
      console.log('\n💡 App ID Issues:');
      console.log('- Make sure App ID is numeric (e.g., 1666280)');
      console.log('- Check your GitHub App settings for the correct ID');
    }
  }
}

testGitHubAuth().catch(console.error);