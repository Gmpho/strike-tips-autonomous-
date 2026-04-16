# Deployment Security

## 🛡️ Security Overview
Strike Tips employs a defense-in-depth approach to secure betting intelligence and bankroll data.

## 🔑 Managing API Keys

To maintain the security of your Strike Tips deployment, you can rotate your API key at any time using the following procedure.

### Generating a New Key
Use the `openssl` toolkit to generate a cryptographically secure random key:
```bash
openssl rand -hex 16
```

### Rotating the Key
To update your environment with a new key and apply the changes:

1. **Update the .env file**:
   Replace the `STRIKE_TIPS_API_KEY` value in your `.env` file with the newly generated key.

2. **Restart the Service**:
   Apply the changes by restarting the container:
   ```bash
   docker-compose down && docker-compose up -d
   ```

3. **Update Integrations**:
   Ensure you update the `X-API-KEY` header in your `claude_desktop_config.json` (or any n8n/REST clients) to match the new key.
EOF
