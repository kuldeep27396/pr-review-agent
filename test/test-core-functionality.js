#!/usr/bin/env node

// Mock test to demonstrate core functionality without real API calls
console.log('🧪 GitHub PR Review Agent - Core Functionality Test\n');

// Mock data similar to what would come from GitHub
const mockPRData = {
  pull_request: {
    number: 123,
    title: 'Add user authentication feature',
    body: 'This PR implements JWT-based authentication with password hashing',
    html_url: 'https://github.com/test/repo/pull/123'
  },
  repository: {
    name: 'awesome-app',
    owner: { login: 'developer' }
  }
};

const mockFiles = [
  {
    filename: 'src/auth.js',
    status: 'added',
    additions: 45,
    deletions: 0,
    content: `
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

function hashPassword(password) {
  return bcrypt.hash(password, 10);
}

function generateToken(userId) {
  return jwt.sign({ userId }, process.env.SECRET_KEY);
}

// Potential issue: Secret key could be undefined
function validateToken(token) {
  return jwt.verify(token, process.env.SECRET_KEY);
}

module.exports = { hashPassword, generateToken, validateToken };
`
  },
  {
    filename: 'src/login.js',
    status: 'modified',
    additions: 12,
    deletions: 3,
    content: `
const { validateToken } = require('./auth');

// Security issue: No rate limiting
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  
  // Potential SQL injection if not using prepared statements
  const user = await db.query('SELECT * FROM users WHERE username = ' + username);
  
  if (user && bcrypt.compare(password, user.password)) {
    const token = generateToken(user.id);
    res.json({ token });
  } else {
    res.status(401).json({ error: 'Invalid credentials' });
  }
});
`
  }
];

console.log('📋 PR Information:');
console.log(`Title: ${mockPRData.pull_request.title}`);
console.log(`Repository: ${mockPRData.repository.owner.login}/${mockPRData.repository.name}`);
console.log(`Files changed: ${mockFiles.length}`);

console.log('\n🔍 File Analysis:');
mockFiles.forEach((file, index) => {
  console.log(`\n${index + 1}. ${file.filename} (${file.status})`);
  console.log(`   +${file.additions} -${file.deletions} lines`);
});

console.log('\n🤖 Simulated AI Analysis Results:');

// Simulate what the AI would find
const mockAnalysis = [
  {
    file: 'src/auth.js',
    issues: [
      {
        line: 10,
        type: 'security',
        severity: 'high',
        message: 'Environment variable SECRET_KEY might be undefined, leading to security vulnerabilities',
        suggestion: 'Add validation: if (!process.env.SECRET_KEY) throw new Error("SECRET_KEY is required")'
      }
    ]
  },
  {
    file: 'src/login.js', 
    issues: [
      {
        line: 6,
        type: 'security',
        severity: 'high',
        message: 'Potential SQL injection vulnerability with string concatenation',
        suggestion: 'Use parameterized queries: db.query("SELECT * FROM users WHERE username = ?", [username])'
      },
      {
        line: 4,
        type: 'security',
        severity: 'medium',
        message: 'No rate limiting on login endpoint - vulnerable to brute force attacks',
        suggestion: 'Implement rate limiting with express-rate-limit middleware'
      }
    ]
  }
];

mockAnalysis.forEach(analysis => {
  console.log(`\n📁 ${analysis.file}:`);
  analysis.issues.forEach(issue => {
    const severity = issue.severity === 'high' ? '🔴' : issue.severity === 'medium' ? '🟡' : '🟢';
    const type = issue.type === 'security' ? '🔒' : issue.type === 'bug' ? '🐛' : '💭';
    
    console.log(`   ${severity} ${type} Line ${issue.line}: ${issue.message}`);
    console.log(`   💡 Suggestion: ${issue.suggestion}`);
  });
});

console.log('\n📊 Overall Assessment:');
const totalIssues = mockAnalysis.reduce((sum, analysis) => sum + analysis.issues.length, 0);
const highSeverityIssues = mockAnalysis.reduce((sum, analysis) => 
  sum + analysis.issues.filter(issue => issue.severity === 'high').length, 0);

if (highSeverityIssues > 0) {
  console.log('🔴 REQUEST_CHANGES - Critical security issues found');
} else if (totalIssues > 0) {
  console.log('🟡 COMMENT - Issues found that should be addressed');
} else {
  console.log('🟢 APPROVE - No issues found');
}

console.log(`\n📈 Statistics:`);
console.log(`- Total issues found: ${totalIssues}`);
console.log(`- High severity: ${highSeverityIssues}`);
console.log(`- Files reviewed: ${mockFiles.length}`);

console.log('\n💬 Generated Review Summary:');
console.log('This PR implements authentication functionality with JWT tokens and password hashing.');
console.log('However, there are several critical security issues that need to be addressed:');
console.log('1. Potential SQL injection vulnerability in the login endpoint');
console.log('2. Missing validation for environment variables');
console.log('3. No rate limiting protection against brute force attacks');
console.log('\nPlease address these security concerns before merging.');

console.log('\n✅ Test completed! This demonstrates how the AI would analyze real PRs.');
console.log('🚀 In production, this analysis would be posted as GitHub PR review comments.');