#!/usr/bin/env node

require('dotenv').config();

console.log('🔍 GitHub PR Review Agent - Environment Validation\n');

const requiredEnvVars = [
  {
    name: 'GITHUB_APP_ID',
    description: 'Your GitHub App ID',
    validation: (value) => /^\d+$/.test(value)
  },
  {
    name: 'GITHUB_PRIVATE_KEY',
    description: 'Your GitHub App Private Key (PEM format)',
    validation: (value) => value.includes('-----BEGIN') && value.includes('-----END')
  },
  {
    name: 'GITHUB_WEBHOOK_SECRET',
    description: 'Your GitHub App Webhook Secret',
    validation: (value) => value.length >= 8
  },
  {
    name: 'GROQ_API_KEY',
    description: 'Your Groq API Key',
    validation: (value) => value.startsWith('gsk_')
  }
];

const optionalEnvVars = [
  'PORT',
  'NODE_ENV',
  'MAX_FILES_TO_REVIEW',
  'MAX_FILE_SIZE_KB',
  'REVIEW_TIMEOUT_MS',
  'LOG_LEVEL'
];

let allValid = true;

console.log('📋 Required Environment Variables:');
console.log('='.repeat(50));

requiredEnvVars.forEach(({ name, description, validation }) => {
  const value = process.env[name];
  
  if (!value) {
    console.log(`❌ ${name}: Missing`);
    console.log(`   Description: ${description}`);
    allValid = false;
  } else if (!validation(value)) {
    console.log(`⚠️  ${name}: Invalid format`);
    console.log(`   Description: ${description}`);
    allValid = false;
  } else {
    console.log(`✅ ${name}: Valid`);
  }
});

console.log('\n📋 Optional Environment Variables:');
console.log('='.repeat(50));

optionalEnvVars.forEach(name => {
  const value = process.env[name];
  if (value) {
    console.log(`✅ ${name}: ${value}`);
  } else {
    console.log(`➖ ${name}: Using default`);
  }
});

console.log('\n📊 Validation Summary:');
console.log('='.repeat(50));

if (allValid) {
  console.log('🎉 All required environment variables are properly configured!');
  console.log('\n🚀 You can now start the application with: npm start');
  process.exit(0);
} else {
  console.log('❌ Some environment variables are missing or invalid.');
  console.log('\n📖 Setup Instructions:');
  console.log('1. Copy .env.example to .env');
  console.log('2. Fill in your GitHub App credentials');
  console.log('3. Add your Groq API key');
  console.log('4. Run this validation again: node scripts/validate-env.js');
  console.log('\n📚 Documentation:');
  console.log('- README.md for general setup');
  console.log('- docs/RAILWAY_DEPLOYMENT.md for Railway deployment');
  console.log('- Run: node scripts/setup-github-app.js for interactive setup');
  process.exit(1);
}