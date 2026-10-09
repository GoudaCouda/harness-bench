FROM node:22-alpine
WORKDIR /app
COPY package.json ./
COPY app ./app
COPY config/default.json ./config/default.json
COPY vendor/licenses/runtime.txt ./licenses/runtime.txt
CMD ["node", "app/server.js"]
