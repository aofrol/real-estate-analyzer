FROM node:20-alpine

WORKDIR /app

# Install dependencies first (Docker layer cache)
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Next.js dev server on port 3000 (docker-compose maps to host :5000)
EXPOSE 3000
CMD ["npm", "run", "dev"]
