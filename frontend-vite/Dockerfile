FROM node:20-alpine

ENV NODE_ENV=production
ENV npm_config_timeout=300000

WORKDIR /app

# Install curl for health checks
RUN apk add --no-cache curl

# Copy package.json and package-lock.json for better caching
COPY package*.json ./

# Install dependencies with clean platform-specific packages
RUN npm ci --include=dev --no-audit --no-fund

# Copy source code excluding node_modules
COPY . .
# Remove any copied node_modules to ensure clean install
RUN rm -rf node_modules && npm ci --include=dev --no-audit --no-fund

# Build the Vite app
RUN npm run build

# Serve the built app
EXPOSE 3000

CMD ["npm", "run", "serve"]
