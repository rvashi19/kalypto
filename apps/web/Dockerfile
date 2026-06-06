FROM node:20-alpine

WORKDIR /workspace

RUN corepack enable

COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json components.json /workspace/
COPY apps/web/package.json /workspace/apps/web/package.json
COPY packages/shared/package.json /workspace/packages/shared/package.json
COPY packages/ui/package.json /workspace/packages/ui/package.json

RUN pnpm install --no-frozen-lockfile

COPY apps/web /workspace/apps/web
COPY packages/shared /workspace/packages/shared
COPY packages/ui /workspace/packages/ui

EXPOSE 5173

CMD ["pnpm", "--filter", "web", "dev", "--host", "0.0.0.0", "--port", "5173"]
