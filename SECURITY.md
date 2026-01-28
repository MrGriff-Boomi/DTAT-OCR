# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in DTAT OCR, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainer directly or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Considerations

### File Processing

- DTAT OCR processes user-uploaded files which may contain malicious content
- Files are processed in isolated temporary directories
- Original files are stored as base64 in the database (be mindful of database access)

### API Security

- The API does not include authentication by default
- For production deployments, add authentication middleware
- Consider rate limiting for public-facing deployments

### Docker Security

- Docker images run as non-root where possible
- Model weights are baked into images (no runtime downloads in offline mode)
- Use Docker secrets for sensitive environment variables

### AWS Deployment

- Use IAM roles instead of access keys when possible
- Restrict Textract permissions to only what's needed
- Enable VPC endpoints to keep traffic private

## Best Practices for Deployment

1. Run behind a reverse proxy (nginx, Traefik) with TLS
2. Enable authentication for the API
3. Use environment variables for secrets (never commit them)
4. Regularly update dependencies for security patches
5. Monitor logs for suspicious activity
