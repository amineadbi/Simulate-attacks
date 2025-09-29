FROM node:20-alpine

ENV NODE_ENV=production
ENV NEXT_PUBLIC_MCP_BASE_URL=http://backend:8000
ENV npm_config_timeout=600000
ENV npm_config_registry=https://registry.npmjs.org/

WORKDIR /app

# Install curl for health checks
RUN apk add --no-cache curl

# Copy package.json and package-lock.json for better caching
COPY frontend/package*.json ./

# Install dependencies with increased timeout and optimizations
RUN npm ci --include=dev --no-audit --no-fund --timeout=600000

# Copy frontend source files but exclude node_modules
COPY frontend .
# Remove any copied node_modules to ensure clean install
RUN rm -rf node_modules && npm ci --include=dev --no-audit --no-fund --timeout=600000

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]