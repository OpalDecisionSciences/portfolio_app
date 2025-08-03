#!/bin/bash
# Redis production entrypoint with secure environment variable substitution

# Substitute environment variables in redis.conf template
envsubst < /usr/local/etc/redis/redis.conf.template > /usr/local/etc/redis/redis.conf

# Start Redis with the processed configuration
exec redis-server /usr/local/etc/redis/redis.conf