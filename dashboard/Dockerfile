FROM node:22-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
# The lock was produced on Windows and omits two Linux-only optional packages.
# npm install resolves those platform-specific optional entries inside the image.
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM node:22-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app ./

EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["npm", "run", "start", "--", "--host", "0.0.0.0", "--port", "3000"]
