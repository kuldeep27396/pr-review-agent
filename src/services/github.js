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
      
      // Create Octokit with App authentication directly
      const octokit = new Octokit({
        authStrategy: createAppAuth,
        auth: {
          appId: parseInt(this.appId),
          privateKey: this.privateKey.replace(/\\n/g, '\n'),
          installationId: parseInt(installationId),
        },
      });
      
      logger.info(`🔍 Auth config - App ID: ${parseInt(this.appId)}, Installation ID: ${parseInt(installationId)}`);
      logger.info('✅ Octokit instance created with App authentication');

      // Test the authentication by getting installation info
      logger.info('🧪 Testing GitHub authentication...');
      logger.info(`🔍 Making API call to get installation ${installationId}...`);
      
      const installation = await octokit.rest.apps.getInstallation({
        installation_id: parseInt(installationId),
      });
      
      logger.info(`✅ Installation retrieved: ${installation.data.account.login}`);
      logger.info('✅ GitHub authentication successful');
      
      return octokit;

    } catch (error) {
      logger.error('❌ GitHub authentication failed:');
      logger.error(`App ID: ${this.appId}`);
      logger.error(`Installation ID: ${installationId}`);
      logger.error(`Private Key length: ${this.privateKey.length}`);
      logger.error(`Private Key starts with: ${this.privateKey.substring(0, 50)}...`);
      logger.error(`Error: ${error.message}`);
      
      if (error.message.includes('PEM')) {
        logger.error('🔑 Private key format issue detected');
        logger.error('Make sure the private key includes proper line breaks');
      }
      
      if (error.message.includes('installation')) {
        logger.error('🏠 Installation issue detected');
        logger.error('Make sure the GitHub App is installed on the repository');
      }
      
      if (error.message.includes('Bad credentials')) {
        logger.error('🔐 Credentials issue detected');
        logger.error('Verify App ID and Private Key are correct');
      }
      
      throw error;
    }
  }

  async getPRFiles(octokit, owner, repo, prNumber) {
    try {
      // First get PR details to get the head SHA
      const { data: pr } = await octokit.rest.pulls.get({
        owner,
        repo,
        pull_number: prNumber,
      });

      const { data: files } = await octokit.rest.pulls.listFiles({
        owner,
        repo,
        pull_number: prNumber,
      });

      logger.info(`📊 PR #${prNumber} has ${files.length} changed files`);

      const maxFiles = parseInt(process.env.MAX_FILES_TO_REVIEW) || 10;
      const maxFileSize = (parseInt(process.env.MAX_FILE_SIZE_KB) || 100) * 1024;

      const filteredFiles = files
        .filter(file => {
          if (file.status === 'removed') return false;
          if (file.additions + file.deletions > maxFileSize / 10) return false;
          return this.isReviewableFile(file.filename);
        })
        .slice(0, maxFiles);

      logger.info(`🔍 Found ${filteredFiles.length} reviewable files after filtering`);

      const filesWithContent = await Promise.all(
        filteredFiles.map(async (file) => {
          try {
            // Use PR head SHA instead of individual file SHA for better reliability
            const { data: content } = await octokit.rest.repos.getContent({
              owner,
              repo,
              path: file.filename,
              ref: pr.head.sha,
            });

            logger.info(`✅ Fetched content for ${file.filename} (${content.size} bytes)`);

            return {
              ...file,
              content: Buffer.from(content.content, 'base64').toString('utf-8'),
            };
          } catch (error) {
            logger.warn(`Could not fetch content for ${file.filename}:`, error.message);
            
            // Try fallback: fetch from PR head branch name
            try {
              const { data: content } = await octokit.rest.repos.getContent({
                owner,
                repo,
                path: file.filename,
                ref: pr.head.ref,
              });
              
              logger.info(`✅ Fetched content for ${file.filename} using branch ref (${content.size} bytes)`);
              
              return {
                ...file,
                content: Buffer.from(content.content, 'base64').toString('utf-8'),
              };
            } catch (fallbackError) {
              logger.warn(`Fallback also failed for ${file.filename}:`, fallbackError.message);
              return {
                ...file,
                content: null,
              };
            }
          }
        })
      );

      const validFiles = filesWithContent.filter(file => file.content !== null);
      logger.info(`📝 Successfully fetched content for ${validFiles.length} files`);
      
      return validFiles;
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