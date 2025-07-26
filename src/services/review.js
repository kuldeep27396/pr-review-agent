const OpenAIService = require('./openai');
const { logger } = require('../utils/logger');

class ReviewService {
  constructor() {
    this.openaiService = new OpenAIService();
  }

  async reviewPR(files, pullRequest) {
    try {
      if (!files || files.length === 0) {
        logger.info('No files to review');
        return null;
      }

      logger.info(`Starting review of ${files.length} files for PR: ${pullRequest.title}`);

      const fileAnalyses = await Promise.all(
        files.map(async (file) => {
          const analysis = await this.openaiService.analyzeCode(file, pullRequest);
          return analysis;
        })
      );

      const validAnalyses = fileAnalyses.filter(analysis => analysis !== null);

      if (validAnalyses.length === 0) {
        logger.warn('No valid analyses returned');
        return null;
      }

      const overallSummary = await this.openaiService.generateOverallSummary(validAnalyses, pullRequest);

      const comments = this.generateComments(validAnalyses);

      const overallAssessment = this.determineOverallAssessment(validAnalyses);

      return {
        event: overallAssessment,
        summary: overallSummary,
        comments: comments,
        fileCount: files.length,
        reviewedCount: validAnalyses.length,
        totalIssues: comments.length
      };

    } catch (error) {
      logger.error('Error during PR review:', error);
      throw error;
    }
  }

  generateComments(analyses) {
    const comments = [];

    analyses.forEach(analysis => {
      if (analysis.issues && analysis.issues.length > 0) {
        analysis.issues.forEach(issue => {
          const severity = this.getSeverityEmoji(issue.severity);
          const type = this.getTypeEmoji(issue.type);
          
          const comment = {
            path: analysis.file,
            line: issue.line,
            body: `${severity} ${type} **${issue.type.toUpperCase()}** (${issue.severity})\n\n${issue.message}\n\n${issue.suggestion ? `💡 **Suggestion:** ${issue.suggestion}` : ''}`
          };

          comments.push(comment);
        });
      }
    });

    return comments;
  }

  determineOverallAssessment(analyses) {
    const hasHighSeverityIssues = analyses.some(analysis => 
      analysis.issues.some(issue => issue.severity === 'high')
    );

    const hasSecurityIssues = analyses.some(analysis =>
      analysis.issues.some(issue => issue.type === 'security')
    );

    const hasBugIssues = analyses.some(analysis =>
      analysis.issues.some(issue => issue.type === 'bug')
    );

    if (hasHighSeverityIssues || hasSecurityIssues || hasBugIssues) {
      return 'REQUEST_CHANGES';
    }

    const hasAnyIssues = analyses.some(analysis => analysis.issues.length > 0);
    
    if (hasAnyIssues) {
      return 'COMMENT';
    }

    return 'APPROVE';
  }

  getSeverityEmoji(severity) {
    switch (severity?.toLowerCase()) {
      case 'high': return '🔴';
      case 'medium': return '🟡';
      case 'low': return '🟢';
      default: return '⚪';
    }
  }

  getTypeEmoji(type) {
    switch (type?.toLowerCase()) {
      case 'bug': return '🐛';
      case 'security': return '🔒';
      case 'performance': return '⚡';
      case 'style': return '🎨';
      case 'best-practice': return '✅';
      default: return '💭';
    }
  }
}

module.exports = ReviewService;