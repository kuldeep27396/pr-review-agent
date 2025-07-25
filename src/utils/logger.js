const fs = require('fs');
const path = require('path');

class Logger {
  constructor() {
    this.logLevel = process.env.LOG_LEVEL || 'info';
    this.logDir = path.join(process.cwd(), 'logs');
    this.canWriteFiles = false;
    
    // Try to create logs directory, but don't fail if we can't
    try {
      if (!fs.existsSync(this.logDir)) {
        fs.mkdirSync(this.logDir, { recursive: true });
      }
      // Test if we can write by creating a test file
      const testFile = path.join(this.logDir, 'test.log');
      fs.writeFileSync(testFile, 'test');
      fs.unlinkSync(testFile);
      this.canWriteFiles = true;
    } catch (error) {
      console.warn('Cannot create log files, logging to console only:', error.message);
      this.canWriteFiles = false;
    }

    this.levels = {
      error: 0,
      warn: 1,
      info: 2,
      debug: 3
    };
  }

  formatMessage(level, message, ...args) {
    const timestamp = new Date().toISOString();
    const formattedArgs = args.map(arg => 
      typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
    ).join(' ');
    
    return `[${timestamp}] [${level.toUpperCase()}] ${message} ${formattedArgs}`;
  }

  writeToFile(level, formattedMessage) {
    // Only attempt to write to files if we can
    if (!this.canWriteFiles) {
      return;
    }
    
    const logFile = path.join(this.logDir, `${level}.log`);
    const allLogFile = path.join(this.logDir, 'all.log');
    
    try {
      fs.appendFileSync(logFile, formattedMessage + '\n');
      fs.appendFileSync(allLogFile, formattedMessage + '\n');
    } catch (error) {
      // If we suddenly can't write, disable file logging
      this.canWriteFiles = false;
      console.warn('Log file writing disabled due to error:', error.message);
    }
  }

  shouldLog(level) {
    return this.levels[level] <= this.levels[this.logLevel];
  }

  error(message, ...args) {
    if (this.shouldLog('error')) {
      const formatted = this.formatMessage('error', message, ...args);
      console.error('\x1b[31m%s\x1b[0m', formatted);
      this.writeToFile('error', formatted);
    }
  }

  warn(message, ...args) {
    if (this.shouldLog('warn')) {
      const formatted = this.formatMessage('warn', message, ...args);
      console.warn('\x1b[33m%s\x1b[0m', formatted);
      this.writeToFile('warn', formatted);
    }
  }

  info(message, ...args) {
    if (this.shouldLog('info')) {
      const formatted = this.formatMessage('info', message, ...args);
      console.log('\x1b[36m%s\x1b[0m', formatted);
      this.writeToFile('info', formatted);
    }
  }

  debug(message, ...args) {
    if (this.shouldLog('debug')) {
      const formatted = this.formatMessage('debug', message, ...args);
      console.log('\x1b[37m%s\x1b[0m', formatted);
      this.writeToFile('debug', formatted);
    }
  }
}

const logger = new Logger();

module.exports = { logger };