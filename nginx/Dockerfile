FROM nginx:alpine
RUN rm -f /etc/nginx/conf.d/default.conf
COPY default.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -qO /dev/null http://localhost:80/ || exit 1
