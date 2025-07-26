const { createAppAuth } = require('@octokit/auth-app');
const { Octokit } = require('@octokit/rest');
const { logger } = require('../utils/logger');

class GitHubService {
  constructor() {
    this.appId = process.env.GITHUB_APP_ID;
    this.privateKey = process.env.GITHUB_PRIVATE_KEY;
    
    if (!this.appId || !this.privateKey) {
      throw new Error('GitHub App ID and Private Key are required');
    }

    // Validate App ID is numeric
    if (!/^\d+$/.test(this.appId)) {
      throw new Error(`Invalid GitHub App ID format: ${this.appId}. Should be numeric.`);
    }

    // Validate Private Key format
    if (!this.privateKey.includes('BEGIN') || !this.privateKey.includes('END')) {
      throw new Error('Invalid GitHub Private Key format. Should be a PEM format key.');
    }

    logger.info(`🔧 GitHub App initialized with ID: ${this.appId}`);
  }

  async getInstallationOctokit(installationId) {
    try {
      logger.info(`🔑 Creating GitHub App auth for installation: ${installationId}`);
      
      // Test if we can create the auth object
      const auth = createAppAuth({
        appId: parseInt(this.appId), // Ensure it's a number
        privateKey: this.privateKey.replace(/\\n/g, '\n'), // Handle escaped newlines
        installationId: installationId,
      });

      logger.info('✅ GitHub App auth created successfully');
      
      // Try using the auth object directly instead of extracting token
      logger.info('🔍 Creating Octokit with auth object...');
      const octokit = new Octokit({
        auth,
      });
      
      // Also try manual token approach for comparison
      logger.info('🔍 Getting installation token for debugging...');
      try {
        const { token } = await auth({ type: 'installation' });
        logger.info(`✅ Installation token obtained: ${token.substring(0, 20)}...`);
        logger.info(`🔍 Token type: ${typeof token}`);
        logger.info(`🔍 Token length: ${token.length}`);
        logger.info(`🔍 Token ends with: ...${token.substring(token.length - 10)}`);
        
        // Validate token format
        if (typeof token !== 'string' || !token.startsWith('ghs_')) {
          logger.error(`❌ Invalid token format. Expected string starting with 'ghs_', got: ${typeof token} - ${token.substring(0, 50)}`);
        } else {
          logger.info('✅ Token format validation passed');
        }
      } catch (tokenError) {
        logger.error('❌ Token extraction failed:', tokenError.message);
      }

      // Test the authentication by getting installation info
      logger.info('🧪 Testing GitHub authentication...');
      logger.info(`🔍 Making API call to get installation ${installationId}...`);
      
      try {
        const installation = await octokit.rest.apps.getInstallation({
          installation_id: installationId,
        });
        logger.info(`✅ Installation retrieved: ${installation.data.account.login}`);
      } catch (apiError) {
        logger.error('❌ API call failed:');
        logger.error(`API Error name: ${apiError.name}`);
        logger.error(`API Error message: ${apiError.message}`);
        logger.error(`API Error status: ${apiError.status}`);
        logger.error(`API Error headers: ${JSON.stringify(apiError.response?.headers || {})}`);
        throw apiError;
      }
      
      logger.info('✅ GitHub authentication successful');
      return octokit;

    } catch (error) {
      logger.error('❌ GitHub authentication failed:');
      logger.error(`App ID: ${this.appId}`);
      logger.error(`Installation ID: ${installationId}`);
      logger.error(`Private Key length: ${this.privateKey.length}`);
      logger.error(`Private Key starts with: ${this.privateKey.substring(0, 50)}...`);
      
      if (error.message.includes('PEM')) {
        logger.error('🔑 Private key format issue detected');
        logger.error('Make sure the private key includes proper line breaks');
      }
      
      if (error.message.includes('installation')) {
        logger.error('🏠 Installation issue detected');
        logger.error('Make sure the GitHub App is installed on the repository');
      }
      
      throw error;
    }
  }

  async getPRFiles(octokit, owner, repo, prNumber) {
    try {
      const { data: files } = await octokit.rest.pulls.listFiles({
        owner,
        repo,
        pull_number: prNumber,
      });

      const maxFiles = parseInt(process.env.MAX_FILES_TO_REVIEW) || 10;
      const maxFileSize = (parseInt(process.env.MAX_FILE_SIZE_KB) || 100) * 1024;

      const filteredFiles = files
        .filter(file => {
          if (file.status === 'removed') return false;
          if (file.additions + file.deletions > maxFileSize / 10) return false;
          return this.isReviewableFile(file.filename);
        })
        .slice(0, maxFiles);

      const filesWithContent = await Promise.all(
        filteredFiles.map(async (file) => {
          try {
            const { data: content } = await octokit.rest.repos.getContent({
              owner,
              repo,
              path: file.filename,
              ref: file.sha,
            });

            return {
              ...file,
              content: Buffer.from(content.content, 'base64').toString('utf-8'),
            };
          } catch (error) {
            logger.warn(`Could not fetch content for ${file.filename}:`, error.message);
            return {
              ...file,
              content: null,
            };
          }
        })
      );

      return filesWithContent.filter(file => file.content !== null);
    } catch (error) {
      logger.error('Error fetching PR files:', error);
      throw error;
    }
  }

  isReviewableFile(filename) {
    const reviewableExtensions = [
      '.js', '.jsx', '.ts', '.tsx', '.py', '.java', '.cpp', '.c', '.h',
      '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
      '.vue', '.svelte', '.dart', '.r', '.sql', '.sh', '.yaml', '.yml',
      '.json', '.xml', '.html', '.css', '.scss', '.less'
    ];

    const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));
    return reviewableExtensions.includes(extension);
  }

  async postReview(octokit, owner, repo, prNumber, review) {
    try {
      const reviewData = {
        owner,
        repo,
        pull_number: prNumber,
        event: 'COMMENT',
        body: review.summary,
      };

      if (review.comments && review.comments.length > 0) {
        reviewData.comments = review.comments.map(comment => ({
          path: comment.path,
          line: comment.line,
          body: comment.body,
        }));
      }

      await octokit.rest.pulls.createReview(reviewData);
      logger.info(`Successfully posted review for PR #${prNumber}`);
    } catch (error) {
      logger.error('Error posting review:', error);
      throw error;
    }
  }
}

module.exports = GitHubService;