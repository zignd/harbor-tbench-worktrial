Configure and repair the C-based log aggregator in /app to ensure all log entries are securely signed and that the system can handle production traffic levels.

All ingested logs must be stored in /var/log/aggregator/output with an HMAC-SHA256 signature using the key found in /etc/aggregator/secret.key. The system must be capable of processing a sustained load of 10,000 requests per second with zero packet loss in the metrics log.

The configuration in /app/config.yaml must correctly toggle 'secure_mode' to enable or disable cryptographic signing. The system must demonstrate that the 'secure_mode' flag is respected and that the internal integrity check passes for all ingested data of any length.

Use the provided source code in /app to identify and resolve any bottlenecks or bugs that prevent the system from meeting these security and performance requirements.
