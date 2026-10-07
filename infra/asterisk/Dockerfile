FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends asterisk asterisk-modules gettext-base \
 && rm -rf /var/lib/apt/lists/*

COPY config/ /opt/pinecone/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5060/udp 10000-10100/udp
ENTRYPOINT ["/entrypoint.sh"]
