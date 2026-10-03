FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV NODE_ENV=production
ENV BACKEND_INTERNAL_URL=http://backend:8000
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
