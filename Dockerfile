FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY src/ ./src/

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chmod 755 /app/logs

RUN addgroup -g 1001 -S nodejs
RUN adduser -S nodejs -u 1001

# Give nodejs user permission to write to logs directory
RUN chown -R nodejs:nodejs /app/logs

USER nodejs

EXPOSE 3000

CMD ["npm", "start"]