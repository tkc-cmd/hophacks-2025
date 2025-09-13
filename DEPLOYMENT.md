# Deployment Guide - RxVoice Assistant

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ installed
- API keys for Deepgram, Google Gemini Pro, and ElevenLabs
- Modern web browser with microphone support

### 1. Setup
```bash
# Run the automated setup
./setup.sh

# Verify setup
node test-setup.js
```

### 2. Configure API Keys
Edit `backend/.env` with your API keys:
```env
DEEPGRAM_API_KEY=your_actual_deepgram_key
GEMINI_API_KEY=your_actual_gemini_key  
ELEVENLABS_API_KEY=your_actual_elevenlabs_key
```

### 3. Start the Application

**Terminal 1 - Backend:**
```bash
cd backend
npm run dev
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

### 4. Access the Application
- Frontend: http://localhost:3000
- Backend API: http://localhost:3001

## 🔑 API Keys Setup

### Deepgram (Speech-to-Text)
1. Sign up at [deepgram.com](https://deepgram.com)
2. Create a new project
3. Generate an API key
4. Copy to `DEEPGRAM_API_KEY` in `.env`

### Google Gemini Pro (LLM)
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy to `GEMINI_API_KEY` in `.env`

### ElevenLabs (Text-to-Speech)
1. Register at [elevenlabs.io](https://elevenlabs.io)
2. Go to Profile & API Key
3. Generate an API key
4. Copy to `ELEVENLABS_API_KEY` in `.env`

## 🧪 Testing

### Quick Test
```bash
# Verify setup
node test-setup.js

# Test with sample patient
# Name: John Smith
# DOB: 05/15/1965
# Say: "I want to refill my Metformin"
```

### Full Test Suite
See `TESTING.md` for comprehensive testing scenarios.

## 🏗️ Production Deployment

### Environment Variables
```env
NODE_ENV=production
PORT=3001
DATABASE_PATH=/path/to/production/database.db
```

### Backend Deployment
```bash
# Build for production
cd backend
npm install --production

# Start with PM2
pm2 start server.js --name rxvoice-backend
```

### Frontend Deployment
```bash
# Build for production
cd frontend
npm run build

# Serve with nginx or similar
# Point to build/ directory
```

### Database Setup
```bash
# Create production database directory
mkdir -p /var/lib/rxvoice/database

# Update DATABASE_PATH in .env
DATABASE_PATH=/var/lib/rxvoice/database/pharmacy.db
```

### SSL/HTTPS Setup
- Required for microphone access in production
- Use Let's Encrypt or similar SSL certificate
- Configure reverse proxy (nginx/Apache)

### WebSocket Configuration
```nginx
# nginx configuration for WebSocket
location /api/voice/stream {
    proxy_pass http://localhost:3001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

## 🔒 Security Considerations

### Production Checklist
- [ ] HTTPS enabled
- [ ] API keys secured (environment variables)
- [ ] CORS configured for production domain
- [ ] Rate limiting implemented
- [ ] Input validation enabled
- [ ] Session timeouts configured
- [ ] Error logging setup
- [ ] Database backups scheduled

### HIPAA Compliance Notes
- This is a demo application
- For production healthcare use:
  - Implement proper encryption
  - Add audit logging
  - Ensure data retention policies
  - Add user authentication
  - Implement access controls

## 📊 Monitoring

### Health Checks
```bash
# Backend health
curl http://localhost:3001/api/health

# Voice services health  
curl http://localhost:3001/api/voice/health
```

### Logging
- Application logs: `backend/logs/`
- Error tracking: Consider Sentry or similar
- Performance monitoring: Consider New Relic or similar

### Metrics to Monitor
- WebSocket connection count
- API response times
- Audio processing latency
- Database query performance
- Error rates by endpoint

## 🚨 Troubleshooting

### Common Issues

**1. Microphone not working**
```
Solution: Ensure HTTPS in production, check browser permissions
```

**2. WebSocket connection fails**
```
Solution: Check firewall, verify port 3001 is open
```

**3. API errors**
```
Solution: Verify API keys, check rate limits, monitor quotas
```

**4. Database errors**
```
Solution: Check file permissions, verify database path
```

### Debug Mode
```bash
# Enable debug logging
DEBUG=* npm run dev
```

### Log Files
```bash
# View backend logs
tail -f backend/logs/app.log

# View error logs
tail -f backend/logs/error.log
```

## 🔄 Updates and Maintenance

### Updating Dependencies
```bash
# Backend
cd backend && npm update

# Frontend  
cd frontend && npm update
```

### Database Migrations
```bash
# Backup database
cp database/pharmacy.db database/pharmacy.db.backup

# Run migrations (if any)
node backend/src/database/migrate.js
```

### API Key Rotation
1. Generate new API keys
2. Update `.env` file
3. Restart application
4. Verify functionality
5. Revoke old keys

## 📈 Scaling Considerations

### Horizontal Scaling
- Load balancer for multiple backend instances
- Shared database or database clustering
- Redis for session management
- CDN for frontend assets

### Performance Optimization
- Audio compression for WebSocket streams
- Database connection pooling
- API response caching
- Frontend code splitting

### Cost Optimization
- Monitor API usage and costs
- Implement request caching
- Optimize audio quality vs. bandwidth
- Use appropriate instance sizes

## 🎯 Demo Deployment

### Hackathon Setup
```bash
# Quick demo setup
./setup.sh
# Add API keys to backend/.env
# Start both services
# Demo ready in 5 minutes!
```

### Demo Script
1. Show professional interface
2. Demonstrate voice interaction with John Smith
3. Show error handling with invalid patient
4. Highlight technical features
5. Emphasize healthcare innovation potential

### Backup Plans
- Text input if voice fails
- Pre-recorded demo video
- Static screenshots for worst case

---

## 📞 Support

For issues or questions:
1. Check `TESTING.md` for common scenarios
2. Review logs for error details
3. Verify API key configuration
4. Test with different browsers
5. Check network connectivity

Remember: This is a demo application. For production healthcare use, additional security, compliance, and testing measures are required.

