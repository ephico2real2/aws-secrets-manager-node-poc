# DEV/CI ONLY: the AWS mock (Secrets Manager, STS, CloudTrail + the alarm rule)
# and sns-logger (a local SNS with a screen), in one image.
# Build from the repository root:  docker build -f dev/aws-mock/Dockerfile .
FROM docker.io/library/node:22-alpine
WORKDIR /mock
COPY dev/aws-mock/server.js ./
COPY dev/aws-mock/lib ./lib
COPY dev/aws-mock/rules ./rules
COPY dev/aws-mock/sns-logger ./sns-logger
# Shared with the app, at the same relative paths (no dependencies in either):
COPY backend/src/alerts/recipients.js /backend/src/alerts/recipients.js
COPY backend/src/logship/otlp.js /backend/src/logship/otlp.js
COPY frontend/styles.css /frontend/styles.css
# A data directory the unprivileged user owns (a named volume inherits it).
RUN mkdir -p /data && chown 1000:1000 /data
ENV PORT=4566 HOST=0.0.0.0
USER 1000
EXPOSE 4566 4575
CMD ["node", "server.js"]
