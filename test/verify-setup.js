#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🔍 GitHub PR Review Agent - Setup Verification\n');

// Check file structure
const requiredFiles = [
  'src/index.js',
  'src/services/github.js',
  'src/services/groq.js',
  'src/services/review.js',
  'src/utils/logger.js',
  'package.json',
  '.env.example',
  'README.md'
];

console.log('📁 Checking file structure...');
let allFilesExist = true;

requiredFiles.forEach(file => {
  if (fs.existsSync(file)) {
    console.log(`✅ ${file}`);
  } else {
    console.log(`❌ ${file} - MISSING`);
    allFilesExist = false;
  }
});

// Check dependencies
console.log('\n📦 Checking dependencies...');
try {
  const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  const requiredDeps = ['express', '@octokit/webhooks', '@octokit/rest', 'groq-sdk', 'dotenv'];
  
  requiredDeps.forEach(dep => {
    if (packageJson.dependencies[dep]) {
      console.log(`✅ ${dep} - ${packageJson.dependencies[dep]}`);
    } else {
      console.log(`❌ ${dep} - MISSING`);
      allFilesExist = false;
    }
  });
} catch (error) {
  console.log('❌ Error checking package.json:', error.message);
  allFilesExist = false;
}

// Test service imports
console.log('\n🧪 Testing service imports...');
try {
  // Mock environment variables for testing
  process.env.GITHUB_APP_ID = 'test';
  process.env.GITHUB_PRIVATE_KEY = 'test-key';
  process.env.GITHUB_WEBHOOK_SECRET = 'test-secret';
  process.env.GROQ_API_KEY = 'test-groq-key';
  
  const GitHubService = require('../src/services/github');
  console.log('✅ GitHub service loads correctly');
  
  const GroqService = require('../src/services/groq');
  console.log('✅ Groq service loads correctly');
  
  const ReviewService = require('../src/services/review');
  console.log('✅ Review service loads correctly');
  
  const { logger } = require('../src/utils/logger');
  console.log('✅ Logger utility loads correctly');
  
} catch (error) {
  console.log('❌ Service import error:', error.message);
  allFilesExist = false;
}

// Summary
console.log('\n📊 Verification Summary');
console.log('========================');

if (allFilesExist) {
  console.log('🎉 All checks passed! The GitHub PR Review Agent is ready.');
  console.log('\n🚀 Next steps:');
  console.log('1. Get your GitHub App credentials');
  console.log('2. Get your Groq API key');
  console.log('3. Run: npm run setup');
  console.log('4. Run: npm start');
} else {
  console.log('⚠️  Some issues found. Please check the missing files/dependencies above.');
}

console.log('\n🔧 Available commands:');
console.log('- npm run setup     # Interactive GitHub App setup');
console.log('- npm start         # Start production server');
console.log('- npm run dev       # Start development server with auto-reload');
console.log('- npm run test-server # Start test server with mock data');

// Show environment example
console.log('\n📝 Environment variables needed (.env):');
console.log('GITHUB_APP_ID=your_app_id');
console.log('GITHUB_PRIVATE_KEY=your_private_key');
console.log('GITHUB_WEBHOOK_SECRET=your_webhook_secret');
console.log('GROQ_API_KEY=your_groq_api_key');

console.log('\n✨ Happy coding!');