const OpenAI = require('openai');
const { logger } = require('../utils/logger');

class OpenAIService {
  constructor() {
    this.apiKey = process.env.OPENAI_API_KEY;
    
    if (!this.apiKey) {
      throw new Error('OpenAI API key is required');
    }

    this.openai = new OpenAI({
      apiKey: this.apiKey,
    });

    this.timeout = parseInt(process.env.REVIEW_TIMEOUT_MS) || 30000;
  }

  async analyzeCode(file, pullRequestContext) {
    try {
      const prompt = this.buildReviewPrompt(file, pullRequestContext);
      
      const completion = await Promise.race([
        this.openai.chat.completions.create({
          model: "gpt-3.5-turbo", // Fast and cost-effective
          messages: [
            {
              role: "system",
              content: "You are an expert code reviewer. Analyze the provided code changes and provide constructive feedback. Focus on potential bugs, security issues, performance problems, code quality, and best practices. Be concise but thorough."
            },
            {
              role: "user",
              content: prompt
            }
          ],
          temperature: 0.1,
          max_tokens: 1000,
        }),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('OpenAI API timeout')), this.timeout)
        )
      ]);

      const analysis = completion.choices[0]?.message?.content;
      
      if (!analysis) {
        logger.warn(`No analysis returned for file: ${file.filename}`);
        return null;
      }

      return this.parseAnalysis(analysis, file);
    } catch (error) {
      logger.error(`Error analyzing code for ${file.filename}:`, error);
      return null;
    }
  }

  buildReviewPrompt(file, pullRequestContext) {
    const context = pullRequestContext ? 
      `PR Title: ${pullRequestContext.title}\nPR Description: ${pullRequestContext.body || 'No description provided'}\n\n` : '';

    return `${context}Please review the following code changes:

File: ${file.filename}
Status: ${file.status}
Additions: ${file.additions}
Deletions: ${file.deletions}

Code Content:
\`\`\`
${file.content}
\`\`\`

Please provide:
1. Overall assessment (APPROVE, REQUEST_CHANGES, or COMMENT)
2. Specific issues found with line numbers
3. Suggestions for improvement
4. Security concerns if any
5. Performance considerations

Format your response as JSON with this structure:
{
  "assessment": "APPROVE|REQUEST_CHANGES|COMMENT",
  "issues": [
    {
      "line": number,
      "type": "bug|security|performance|style|best-practice",
      "severity": "high|medium|low",
      "message": "Description of the issue",
      "suggestion": "How to fix it"
    }
  ],
  "summary": "Overall summary of the review"
}`;
  }

  parseAnalysis(analysis, file) {
    try {
      const jsonMatch = analysis.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        return {
          assessment: 'COMMENT',
          issues: [],
          summary: analysis.trim(),
          file: file.filename
        };
      }

      const parsed = JSON.parse(jsonMatch[0]);
      
      return {
        assessment: parsed.assessment || 'COMMENT',
        issues: (parsed.issues || []).map(issue => ({
          ...issue,
          line: parseInt(issue.line) || 1,
          severity: issue.severity || 'medium',
          type: issue.type || 'general'
        })),
        summary: parsed.summary || 'Code review completed',
        file: file.filename
      };
    } catch (error) {
      logger.warn(`Failed to parse analysis JSON for ${file.filename}, using raw text`);
      
      return {
        assessment: 'COMMENT',
        issues: [],
        summary: analysis.trim(),
        file: file.filename
      };
    }
  }

  async generateOverallSummary(fileAnalyses, pullRequest) {
    try {
      const summaryPrompt = `Based on the following individual file reviews, provide an overall summary for the pull request:

PR Title: ${pullRequest.title}
PR Description: ${pullRequest.body || 'No description provided'}

File Reviews:
${fileAnalyses.map(analysis => 
  `- ${analysis.file}: ${analysis.assessment} - ${analysis.summary}`
).join('\n')}

Total Issues Found: ${fileAnalyses.reduce((total, analysis) => total + analysis.issues.length, 0)}

Provide a concise overall assessment and summary of the main points to address.`;

      const completion = await this.openai.chat.completions.create({
        model: "gpt-3.5-turbo",
        messages: [
          {
            role: "system",
            content: "You are an expert code reviewer providing an overall summary of a pull request review."
          },
          {
            role: "user",
            content: summaryPrompt
          }
        ],
        temperature: 0.1,
        max_tokens: 500,
      });

      return completion.choices[0]?.message?.content || 'Review completed successfully.';
    } catch (error) {
      logger.error('Error generating overall summary:', error);
      return 'Review completed. Please check individual file comments for details.';
    }
  }
}

module.exports = OpenAIService;