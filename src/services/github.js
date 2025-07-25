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
  }

  async getInstallationOctokit(installationId) {
    const auth = createAppAuth({
      appId: this.appId,
      privateKey: this.privateKey,
      installationId: installationId,
    });

    return new Octokit({
      auth,
    });
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