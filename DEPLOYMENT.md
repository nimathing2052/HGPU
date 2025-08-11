# 🚀 Railway Deployment Guide

This guide will help you deploy the Hertie GPU Server Automation Flask App to Railway.

## 📋 Prerequisites

1. **GitHub Account**: Your code should be in a GitHub repository
2. **Railway Account**: Sign up at [railway.app](https://railway.app) (free, no credit card required)
3. **GPU Server Access**: Ensure your GPU server (10.1.23.20) is accessible from the internet

## 🎯 Quick Deployment Steps

### 1. **Prepare Your Repository**

Your repository should already contain all necessary files:
- ✅ `Procfile` - Tells Railway how to run the app
- ✅ `runtime.txt` - Specifies Python version
- ✅ `railway.json` - Railway configuration
- ✅ `nixpacks.toml` - Build configuration
- ✅ `requirements.txt` - Python dependencies

### 2. **Deploy to Railway**

1. **Go to [Railway Dashboard](https://railway.app/dashboard)**
2. **Click "New Project"**
3. **Select "Deploy from GitHub repo"**
4. **Choose your repository**
5. **Railway will automatically detect it's a Python app**

### 3. **Configure Environment Variables**

In your Railway project dashboard, go to **Variables** tab and add:

```bash
# GPU Server Configuration
GPU_SERVER_HOST=10.1.23.20
GPU_SERVER_PORT=22

# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_DEBUG=False

# Security (IMPORTANT: Change this!)
SECRET_KEY=your-super-secret-key-change-this-in-production

# Session Configuration
SESSION_TIMEOUT=3600
MAX_SESSIONS_PER_USER=5

# Logging
LOG_LEVEL=INFO
```

### 4. **Deploy**

1. **Railway will automatically build and deploy your app**
2. **Wait for the build to complete** (usually 2-3 minutes)
3. **Your app will be available at the provided URL**

## 🔧 Configuration Details

### **Environment Variables Explained**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GPU_SERVER_HOST` | Your GPU server IP address | 10.1.23.20 | ✅ |
| `GPU_SERVER_PORT` | SSH port for GPU server | 22 | ✅ |
| `SECRET_KEY` | Flask secret key for sessions | - | ✅ |
| `SESSION_TIMEOUT` | Session timeout in seconds | 3600 | ❌ |
| `MAX_SESSIONS_PER_USER` | Max sessions per user | 5 | ❌ |
| `LOG_LEVEL` | Logging level | INFO | ❌ |

### **Railway-Specific Variables**

Railway automatically sets:
- `PORT` - The port your app should listen on
- `RAILWAY_STATIC_URL` - Static file URL (if needed)

## 🔒 Security Considerations

### **SSH Access**

1. **Ensure your GPU server allows connections from Railway's IP ranges**
2. **Consider using SSH key authentication** instead of password
3. **Monitor SSH logs** for any unauthorized access attempts

### **Environment Variables**

1. **Never commit sensitive data** to your repository
2. **Use strong SECRET_KEY** in production
3. **Regularly rotate credentials**

## 🚨 Troubleshooting

### **Common Issues**

#### **Build Fails**
- Check `requirements.txt` for correct dependencies
- Ensure Python version in `runtime.txt` is supported
- Check Railway logs for specific error messages

#### **App Won't Start**
- Verify all environment variables are set
- Check if `PORT` is being used correctly
- Review application logs in Railway dashboard

#### **SSH Connection Fails**
- Verify GPU server is accessible from internet
- Check firewall settings on GPU server
- Ensure SSH credentials are correct

#### **WebSocket Issues**
- Railway supports WebSockets, but check if your app is using the correct port
- Verify CORS settings if needed

### **Logs and Debugging**

1. **Railway Dashboard** → Your Project → **Deployments** → Click on deployment
2. **View logs** in real-time
3. **Check build logs** for any errors

## 📊 Monitoring

### **Railway Metrics**

Railway provides:
- **CPU Usage**
- **Memory Usage**
- **Network I/O**
- **Request logs**

### **Custom Monitoring**

Consider adding:
- **Health check endpoint** (`/health`)
- **Application metrics**
- **Error tracking** (e.g., Sentry)

## 🔄 Updates and Maintenance

### **Automatic Deployments**

Railway automatically deploys when you push to your main branch.

### **Manual Deployments**

1. **Railway Dashboard** → Your Project → **Deployments**
2. **Click "Deploy"** to trigger manual deployment

### **Rollback**

1. **Railway Dashboard** → Your Project → **Deployments**
2. **Click on previous deployment**
3. **Click "Promote"** to rollback

## 💰 Cost Management

### **Free Tier Limits**

- **500 hours/month** (about 20 days)
- **512MB RAM**
- **Shared CPU**

### **Upgrading**

If you need more resources:
1. **Railway Dashboard** → Your Project → **Settings**
2. **Upgrade plan** as needed

## 🎉 Success!

Once deployed, your app will be available at:
```
https://your-app-name.railway.app
```

## 📞 Support

- **Railway Documentation**: [docs.railway.app](https://docs.railway.app)
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)
- **GitHub Issues**: For app-specific issues
