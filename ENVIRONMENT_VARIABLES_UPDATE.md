# Environment Variables Consistency Update

## Overview

This document outlines the changes made to standardize environment variables across the entire portfolio application to use Django's naming convention.

## Problem Solved

**CRITICAL ISSUE**: Database variable naming conflicts that would cause deployment failures:
- Django used: `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`  
- RAG service used: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- .env.example used: `DB_NAME`, `DB_USER`, `DB_PASSWORD` (INCORRECT!)

## Changes Made

### 1. **RAG Service Updates**
**File**: `/rag_service/src/api/main.py`
- **Before**: Used only `POSTGRES_*` variables
- **After**: Supports both Django (`DATABASE_*`) and Docker (`POSTGRES_*`) naming
- **Change**: Added fallback logic: `os.getenv("DATABASE_USER") or os.getenv("POSTGRES_USER", "postgres")`

**File**: `/rag_service/src/embeddings/embedding_generator.py`
- **Before**: Used `DB_*` variables (old naming)
- **After**: Supports both Django (`DATABASE_*`) and legacy (`DB_*`) naming
- **Change**: Updated to prioritize Django naming convention

### 2. **Environment File Updates**
**File**: `.env.example`
- **Before**: Used incorrect `DB_*` naming that didn't match application code
- **After**: Uses correct `DATABASE_*` naming with `POSTGRES_*` for backwards compatibility
- **Added**: Missing variables like `GOOGLE_MAPS_API_KEY`, `CHROMEDRIVER_PATH`, `CHROME_BIN`

**File**: `.env.prod.example`
- **Before**: Only had `POSTGRES_*` variables
- **After**: Has both `DATABASE_*` (primary) and `POSTGRES_*` (Docker compatibility)
- **Added**: Missing application variables and RAG service configuration

**File**: `.env.prod` (NEW)
- **Created**: Production environment file copied from `.env.prod.example`
- **Purpose**: Resolves Docker Compose production configuration errors

### 3. **Documentation Updates**
**File**: `README.md`
- **Before**: Referenced old `DB_PASSWORD` variable
- **After**: Updated to use `DATABASE_PASSWORD`

## Current Environment Variable Standards

### **Primary Naming Convention (Django Compatible)**
```bash
# Database Configuration
DATABASE_NAME=portfolio_db
DATABASE_USER=postgres
DATABASE_PASSWORD=password
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

### **Docker/Legacy Compatibility**
```bash
# Legacy Docker naming (maintained for compatibility)
POSTGRES_DB=portfolio_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
DB_NAME=portfolio_db        # Legacy support
DB_USER=postgres           # Legacy support
DB_PASSWORD=password       # Legacy support
```

### **Complete Environment Variables List**
```bash
# Django Core
DEBUG=True
DJANGO_SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database (Django naming - PRIMARY)
DATABASE_NAME=portfolio_db
DATABASE_USER=postgres
DATABASE_PASSWORD=password
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Database (Docker naming - COMPATIBILITY)
POSTGRES_DB=portfolio_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API Keys
OPENAI_API_KEY=your-openai-api-key
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# Services
RAG_SERVICE_URL=http://localhost:8001

# Application Settings
PORTFOLIO_DATA_DIR=/app/data
PORTFOLIO_SCRAPING_BATCH_SIZE=10
PORTFOLIO_TOKEN_MANAGEMENT_DIR=/app/token_management

# Web Scraping
CHROMEDRIVER_PATH=/usr/bin/chromedriver
CHROME_BIN=/usr/bin/chromium

# Logging
LOG_LEVEL=INFO

# Media and Static Files
MEDIA_ROOT=/app/media
STATIC_ROOT=/app/staticfiles
```

## Backward Compatibility

All changes maintain **backward compatibility**:
- Django settings still work with existing `DATABASE_*` variables
- RAG service now supports both `DATABASE_*` and `POSTGRES_*` 
- Embedding generator supports both `DATABASE_*` and legacy `DB_*`
- Docker Compose files continue using `POSTGRES_*` as expected

## Verification

### **Docker Compose Validation**
✅ Development: `docker-compose config --quiet` - PASSED
✅ Production: `docker-compose -f docker-compose.prod.yml config --quiet` - PASSED

### **Service Compatibility**
✅ Django: Uses `DATABASE_*` variables (unchanged)
✅ RAG Service: Supports both `DATABASE_*` and `POSTGRES_*`
✅ Embedding Generator: Supports both `DATABASE_*` and `DB_*`
✅ Docker Services: Use `POSTGRES_*` variables (unchanged)

## Benefits

1. **🛠️ Developer Experience**: New developers can use `.env.example` without database connection failures
2. **🔧 Production Ready**: `.env.prod` file resolves deployment configuration errors
3. **🔄 Backward Compatible**: Existing configurations continue to work
4. **📋 Standardized**: Consistent naming across all services
5. **🚀 Deployment Safe**: Production Docker Compose configuration is now valid

## Next Steps for Developers

1. **New Setup**: Copy `.env.example` to `.env` and configure your values
2. **Production Deploy**: Copy `.env.prod.example` to `.env.prod` and configure production values
3. **Existing Projects**: No changes needed - backward compatibility maintained

## Files Modified

1. `/rag_service/src/api/main.py` - Added Django variable support
2. `/rag_service/src/embeddings/embedding_generator.py` - Added Django variable support  
3. `.env.example` - Fixed incorrect variable names, added missing variables
4. `.env.prod.example` - Added Django naming convention, added missing variables
5. `.env.prod` - Created production environment file
6. `README.md` - Updated environment variable documentation

This update resolves the critical environment variable inconsistencies and ensures smooth deployment and development experience across all environments.