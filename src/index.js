const express = require('express');
const crypto = require('crypto');
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

const githubService = new GitHubService();
const reviewService = new ReviewService();

// Webhook signature verification
function verifySignature(payload, signature) {
  const expectedSignature = 'sha256=' + crypto
    .createHmac('sha256', process.env.GITHUB_WEBHOOK_SECRET)
    .update(payload, 'utf8')
    .digest('hex');
  
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature)
  );
}

app.use(bodyParser.raw({ type: 'application/json' }));

// Handle webhook requests
app.post('/webhook', async (req, res) => {
  try {
    const signature = req.get('x-hub-signature-256');
    const event = req.get('x-github-event');
    const deliveryId = req.get('x-github-delivery');
    
    if (!signature) {
      logger.warn('No signature provided');
      return res.status(401).send('Unauthorized');
    }
    
    // Verify the webhook signature
    const isValid = verifySignature(req.body, signature);
    if (!isValid) {
      logger.warn('Invalid webhook signature');
      return res.status(401).send('Unauthorized');
    }
    
    // Parse the payload
    const payload = JSON.parse(req.body.toString());
    
    logger.info(`Received ${event} event (delivery: ${deliveryId})`);
    
    // Handle pull request events
    if (event === 'pull_request') {
      const action = payload.action;
      if (action === 'opened' || action === 'synchronize') {
        logger.info(`Processing PR ${action}: ${payload.pull_request.html_url}`);
        await handlePullRequest(payload);
      } else {
        logger.info(`Ignoring PR action: ${action}`);
      }
    } else {
      logger.info(`Ignoring event: ${event}`);
    }
    
    res.status(200).send('OK');
  } catch (error) {
    logger.error('Webhook processing error:', error);
    res.status(500).send('Internal Server Error');
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