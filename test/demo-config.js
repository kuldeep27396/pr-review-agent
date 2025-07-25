#!/usr/bin/env node

console.log('🎯 GitHub PR Review Agent - Configuration Demo\n');

// Show what the .env.example contains
const fs = require('fs');

console.log('📄 Environment Configuration Template (.env.example):');
console.log('=' .repeat(60));
try {
  const envExample = fs.readFileSync('.env.example', 'utf8');
  console.log(envExample);
} catch (error) {
  console.log('Error reading .env.example:', error.message);
}

console.log('\n🔧 Configuration Steps:');
console.log('1. Create GitHub App at: https://github.com/settings/apps/new');
console.log('2. Configure permissions: Contents (read), Pull requests (write)');
console.log('3. Subscribe to events: Pull request, Pull request review');
console.log('4. Download private key and note App ID');
console.log('5. Get Groq API key from: https://console.groq.com/');

console.log('\n🚀 Quick Start Commands:');
console.log('cp .env.example .env          # Copy environment template');
console.log('# Edit .env with your credentials');
console.log('npm start                     # Start the server');

console.log('\n💡 Pro Tips:');
console.log('- Use the setup script: npm run setup (interactive wizard)');
console.log('- Test locally first with: npm run test-server');
console.log('- Deploy with one-click buttons in README.md');
console.log('- Monitor with /health endpoint');

console.log('\n✨ The agent will automatically:');
console.log('🔍 Detect new/updated PRs via webhooks');
console.log('📝 Analyze code changes with Groq AI');
console.log('💬 Post intelligent review comments');
console.log('🎯 Focus on bugs, security, performance, style');
console.log('📊 Provide overall PR assessment');

console.log('\n🌟 Ready to revolutionize your code reviews!');