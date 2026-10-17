# DEV/CI ONLY: the Secrets Manager + STS mock as a container image.
FROM node:22-alpine
WORKDIR /mock
COPY server.js ./
# A data directory the unprivileged user owns (a named volume inherits it).
RUN mkdir -p /data && chown 1000:1000 /data
ENV PORT=4566 HOST=0.0.0.0
USER 1000
EXPOSE 4566
CMD ["node", "server.js"]
