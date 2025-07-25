const express = require('express');
const { Webhooks } = require('@octokit/webhooks');
const bodyParser = require('body-parser');
require('dotenv').config();

const GitHubService = require('./services/github');
const ReviewService = require('./services/review');
const { logger } = require('./utils/logger');

// Validate required environment variables
const requiredEnvVars = [
  'GITHUB_APP_ID',
  'GITHUB_PRIVATE_KEY', 
  'GITHUB_WEBHOOK_SECRET',
  'GROQ_API_KEY'
];

const missingEnvVars = requiredEnvVars.filter(envVar => !process.env[envVar]);

if (missingEnvVars.length > 0) {
  console.error('❌ Missing required environment variables:');
  missingEnvVars.forEach(envVar => {
    console.error(`   - ${envVar}`);
  });
  console.error('\n📖 Please check the deployment documentation:');
  console.error('   - README.md for setup instructions');
  console.error('   - docs/RAILWAY_DEPLOYMENT.md for Railway-specific setup');
  console.error('\n💡 Make sure to set all required environment variables in your deployment platform.');
  process.exit(1);
}

const app = express();
const port = process.env.PORT || 3000;

const webhooks = new Webhooks({
  secret: process.env.GITHUB_WEBHOOK_SECRET,
});

const githubService = new GitHubService();
const reviewService = new ReviewService();

app.use(bodyParser.json());

app.post('/webhook', webhooks.middleware);

webhooks.on('pull_request.opened', async ({ payload }) => {
  try {
    logger.info(`New PR opened: ${payload.pull_request.html_url}`);
    await handlePullRequest(payload);
  } catch (error) {
    logger.error('Error handling PR opened event:', error);
  }
});

webhooks.on('pull_request.synchronize', async ({ payload }) => {
  try {
    logger.info(`PR updated: ${payload.pull_request.html_url}`);
    await handlePullRequest(payload);
  } catch (error) {
    logger.error('Error handling PR synchronize event:', error);
  }
});

async function handlePullRequest(payload) {
  const { pull_request, repository } = payload;
  
  const installationId = payload.installation.id;
  const owner = repository.owner.login;
  const repo = repository.name;
  const prNumber = pull_request.number;

  try {
    const octokit = await githubService.getInstallationOctokit(installationId);
    
    const files = await githubService.getPRFiles(octokit, owner, repo, prNumber);
    
    const review = await reviewService.reviewPR(files, pull_request);
    
    if (review && review.comments.length > 0) {
      await githubService.postReview(octokit, owner, repo, prNumber, review);
      logger.info(`Posted review for PR #${prNumber} in ${owner}/${repo}`);
    } else {
      logger.info(`No issues found in PR #${prNumber} in ${owner}/${repo}`);
    }
  } catch (error) {
    logger.error(`Error processing PR #${prNumber} in ${owner}/${repo}:`, error);
  }
}

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.get('/', (req, res) => {
  res.json({
    name: 'GitHub PR Review Agent',
    description: 'Automated PR reviews powered by Groq AI',
    status: 'running'
  });
});

app.listen(port, () => {
  logger.info(`GitHub PR Review Agent listening on port ${port}`);
  
  // Log configuration status (without exposing sensitive values)
  logger.info('✅ Configuration validated:');
  logger.info(`   - GitHub App ID: ${process.env.GITHUB_APP_ID}`);
  logger.info(`   - Private Key: ${process.env.GITHUB_PRIVATE_KEY ? 'Set' : 'Missing'}`);
  logger.info(`   - Webhook Secret: ${process.env.GITHUB_WEBHOOK_SECRET ? 'Set' : 'Missing'}`);
  logger.info(`   - Groq API Key: ${process.env.GROQ_API_KEY ? 'Set' : 'Missing'}`);
  logger.info(`   - Environment: ${process.env.NODE_ENV || 'development'}`);
  
  logger.info('🚀 Ready to review pull requests!');
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception:', error);
  process.exit(1);
});