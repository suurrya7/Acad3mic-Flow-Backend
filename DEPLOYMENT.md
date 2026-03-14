# Production Deployment Checklist

## Pre-Deployment

### 1. Database Setup
- [ ] Run `schema.sql` in Supabase SQL Editor
- [ ] Run `scripts/database_functions.sql` in Supabase SQL Editor
- [ ] Run `scripts/setup_storage.py` to create storage bucket
- [ ] Verify all RLS policies are enabled

### 2. Environment Configuration
- [ ] Copy `.env.example` to `.env`
- [ ] Set `ENV=production`
- [ ] Configure `SUPABASE_URL` and keys
- [ ] Set `GEMINI_API_KEY`
- [ ] Configure `PAYU_MERCHANT_KEY` and `PAYU_SALT`
- [ ] Set `API_BASE_URL` to production domain
- [ ] Set `PROD_ORIGINS` to frontend domain(s)

### 3. Dependencies
- [ ] Review `requirements.txt` - all versions pinned ✓
- [ ] Test installation: `pip install -r requirements.txt`

### 4. Testing
- [ ] Run automated tests: `pytest tests/`
- [ ] Test health check endpoint: `curl http://localhost:8000/health`
- [ ] Test authentication flow
- [ ] Test payment webhook with test data

## Deployment

### Docker Deployment (Recommended)

```bash
# Build Docker image
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify health
curl http://localhost:8000/health
```

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with production settings
ENV=production uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Post-Deployment

### 1. Monitoring
- [ ] Verify health check returns "healthy"
- [ ] Check logs for errors
- [ ] Monitor API response times
- [ ] Set up error tracking (Sentry, Rollbar, etc.)

### 2. Security Verification
- [ ] Verify security headers present: `curl -I https://api.your-domain.com`
- [ ] Test CORS configuration
- [ ] Verify rate limiting works
- [ ] Test with invalid/malicious payloads

### 3. Functional Testing
- [ ] Create test user account
- [ ] Upload document
- [ ] Create chat and send messages
- [ ] Submit assignment request
- [ ] Test payment flow (sandbox mode)

### 4. Performance
- [ ] Load test with expected traffic
- [ ] Monitor database query performance
- [ ] Check memory usage
- [ ] Verify AI request timeouts work

## Production Configuration

### Nginx Reverse Proxy (Optional)

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### SSL/TLS Setup
- [ ] Obtain SSL certificate (Let's Encrypt)
- [ ] Configure HTTPS redirect
- [ ] Verify HSTS header present

## Maintenance

### Regular Tasks
- Monitor logs: `tail -f logs/app.log`
- Check disk space for log files
- Review transaction records
- Monitor API costs (Gemini, Supabase)
- Update dependencies regularly (test in staging first)

### Backup Strategy
- Supabase handles database backups
- Consider backing up `.env` securely
- Export user data periodically for compliance

## Rollback Plan

If issues occur:
```bash
# Stop services
docker-compose down

# Rollback to previous version
git checkout <previous-tag>
docker-compose build
docker-compose up -d
```

## Support Contacts
- Supabase Support: https://supabase.com/docs/support
- Google AI Support: https://ai.google.dev/support
- PayU Support: (Add your merchant support contact)
