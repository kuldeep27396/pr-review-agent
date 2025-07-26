const GroqService = require('./groq');
const { logger } = require('../utils/logger');

class ReviewService {
  constructor() {
    this.groqService = new GroqService();
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
          const analysis = await this.groqService.analyzeCode(file, pullRequest);
          return analysis;
        })
      );

      const validAnalyses = fileAnalyses.filter(analysis => analysis !== null);

      if (validAnalyses.length === 0) {
        logger.warn('No valid analyses returned');
        return null;
      }

      const comments = this.generateComments(validAnalyses);

      // If no line-specific comments could be made, include issues in summary
      const skippedIssues = this.getSkippedIssues(validAnalyses, comments);
      const enhancedSummary = await this.generateEnhancedSummary(validAnalyses, pullRequest, skippedIssues);

      const overallAssessment = this.determineOverallAssessment(validAnalyses);

      return {
        event: overallAssessment,
        summary: enhancedSummary,
        comments: comments,
        fileCount: files.length,
        reviewedCount: validAnalyses.length,
        totalIssues: comments.length + skippedIssues.length
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
        // Extract valid line numbers from the diff if available
        const validLines = this.extractDiffLines(analysis);
        
        analysis.issues.forEach(issue => {
          const severity = this.getSeverityEmoji(issue.severity);
          const type = this.getTypeEmoji(issue.type);
          
          // Only include comments for lines that are part of the diff
          // If no valid lines found or line is not in diff, skip line-specific comment
          if (validLines.length === 0 || !validLines.includes(issue.line)) {
            logger.warn(`Skipping line-specific comment for ${analysis.file}:${issue.line} - not in diff`);
            return; // Skip this comment
          }
          
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

  extractDiffLines(analysis) {
    // Extract line numbers from patch/diff information
    if (!analysis.patch) {
      logger.warn(`No patch information available for ${analysis.file}`);
      return [];
    }

    const lines = [];
    const patchLines = analysis.patch.split('\n');
    let currentLine = 0;

    logger.info(`🔍 Parsing diff for ${analysis.file}:`);
    logger.info(`Patch: ${analysis.patch.substring(0, 200)}...`);

    for (const line of patchLines) {
      // Parse diff hunk headers like @@ -1,7 +1,8 @@
      const hunkMatch = line.match(/^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/);
      if (hunkMatch) {
        currentLine = parseInt(hunkMatch[1]);
        logger.info(`📍 Found hunk starting at line ${currentLine}`);
        continue;
      }

      // Skip file headers
      if (line.startsWith('+++') || line.startsWith('---')) {
        continue;
      }

      // Track line numbers for added/modified lines (+ prefix) and context lines (space prefix)
      if (line.startsWith('+')) {
        lines.push(currentLine);
        logger.info(`➕ Added line ${currentLine}: ${line.substring(0, 50)}`);
        currentLine++;
      } else if (line.startsWith(' ')) {
        lines.push(currentLine);
        logger.info(`📄 Context line ${currentLine}: ${line.substring(0, 50)}`);
        currentLine++;
      } else if (line.startsWith('-')) {
        // For deleted lines (-), don't increment currentLine as they don't exist in new version
        logger.info(`➖ Deleted line (not counting): ${line.substring(0, 50)}`);
      }
    }

    logger.info(`🔢 Valid diff lines for ${analysis.file}: [${lines.join(', ')}]`);
    return lines;
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

  getSkippedIssues(analyses, postedComments) {
    const skippedIssues = [];
    const postedLines = new Set(postedComments.map(c => `${c.path}:${c.line}`));

    analyses.forEach(analysis => {
      if (analysis.issues && analysis.issues.length > 0) {
        analysis.issues.forEach(issue => {
          const issueKey = `${analysis.file}:${issue.line}`;
          if (!postedLines.has(issueKey)) {
            skippedIssues.push({
              ...issue,
              file: analysis.file
            });
          }
        });
      }
    });

    return skippedIssues;
  }

  async generateEnhancedSummary(analyses, pullRequest, skippedIssues) {
    let baseSummary = await this.groqService.generateOverallSummary(analyses, pullRequest);

    if (skippedIssues.length > 0) {
      const skippedSummary = skippedIssues.map(issue => {
        const severity = this.getSeverityEmoji(issue.severity);
        const type = this.getTypeEmoji(issue.type);
        return `${severity} ${type} **${issue.file}:${issue.line}** - ${issue.message}`;
      }).join('\n');

      baseSummary += `\n\n**Additional Issues Found:**\n${skippedSummary}\n\n*Note: Some issues couldn't be posted as line-specific comments because they reference lines not in the diff.*`;
    }

    return baseSummary;
  }
}

module.exports = ReviewService;