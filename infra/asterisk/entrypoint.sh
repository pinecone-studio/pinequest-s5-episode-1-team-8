#!/bin/sh
set -e

if [ -z "$HOST_IP" ]; then
  echo "АЛДАА: HOST_IP тохируулаагүй байна (.env файлд лаптопын IP-г бич)"
  exit 1
fi

# Тохиргоонд лаптопын IP болон нууц үгийг оруулна
for f in pjsip.conf extensions.conf rtp.conf modules.conf; do
  envsubst '$HOST_IP $PHONE_PASSWORD $AI_HOST $AI_PORT' \
    < /opt/pinecone/$f > /etc/asterisk/$f
done

mkdir -p /var/run/asterisk
rm -f /var/run/asterisk/asterisk.ctl
chown -R asterisk:asterisk /etc/asterisk /var/lib/asterisk /var/run/asterisk \
  /var/log/asterisk /var/spool/asterisk

echo "Asterisk эхэлж байна. HOST_IP=$HOST_IP"
exec asterisk -f -vvv -U asterisk -G asterisk
