# Portfolio Application - Advanced Restaurant RAG System

An advanced portfolio application that combines web scraping, RAG (Retrieval-Augmented Generation), and Django to create an intelligent restaurant discovery and query system.

## 🏗️ Architecture Overview

```
Portfolio Application
├── Django Web App (Main Interface)
├── FastAPI RAG Service (Intelligent Queries)
├── Data Pipeline (Scraping & Processing)
├── Shared Components (Token Management)
└── Vector Database (pgvector)
```

## 🚀 Features

### Core Features
- **Restaurant Discovery**: Comprehensive database of restaurants with detailed information
- **Intelligent Search**: RAG-powered conversational search and recommendations
- **Web Scraping**: Automated data collection from restaurant websites
- **Token Management**: Optimized OpenAI API usage with automatic model switching
- **Multi-language Support**: Automatic translation and language detection

### Advanced Features
- **Vector Embeddings**: Semantic search using pgvector
- **Conversation Memory**: Persistent chat sessions with Redis
- **Background Processing**: Celery for asynchronous tasks
- **Admin Interface**: Django admin for content management
- **API Endpoints**: RESTful APIs for external integrations

## 🛠️ Technology Stack

### Backend
- **Django 4.2**: Web framework and admin interface
- **FastAPI**: High-performance RAG service
- **PostgreSQL + pgvector**: Vector database for embeddings
- **Redis**: Session management and caching
- **Celery**: Background task processing

### AI/ML
- **OpenAI GPT-4o/4o-mini**: Language models
- **LangChain**: RAG orchestration
- **tiktoken**: Token counting and optimization
- **OpenAI Embeddings**: Vector generation

### Web Scraping
- **Selenium**: Web automation and scraping
- **BeautifulSoup**: HTML parsing
- **Language Detection**: Multi-language support

### Infrastructure
- **Docker**: Containerization
- **Nginx**: Reverse proxy
- **Gunicorn**: WSGI server

## 📦 Installation

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- OpenAI API Key

### Quick Start with Docker

1. **Clone the repository**
```bash
git clone <repository-url>
cd portfolio_app
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration, especially OPENAI_API_KEY
```

3. **Start the application**
```bash
docker-compose up -d
```

4. **Run migrations**
```bash
docker-compose exec web python manage.py migrate
```

5. **Create superuser**
```bash
docker-compose exec web python manage.py createsuperuser
```

6. **Access the application**
- Web Interface: http://localhost:8000
- RAG API: http://localhost:8001
- Admin Interface: http://localhost:8000/admin
- Celery Flower: http://localhost:5555

### Local Development Setup

1. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up PostgreSQL with pgvector**
```bash
# Install PostgreSQL and pgvector extension
# Create database: portfolio_db
```

4. **Set up Redis**
```bash
# Install and start Redis server
redis-server
```

5. **Run migrations**
```bash
cd django_app/src
python manage.py migrate
```

6. **Start services**
```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: RAG Service
cd rag_service/src
uvicorn api.main:app --reload --port 8001

# Terminal 3: Celery Worker
cd django_app/src
celery -A portfolio_project worker --loglevel=info

# Terminal 4: Celery Beat
cd django_app/src
celery -A portfolio_project beat --loglevel=info
```

## 🔧 Configuration

### Environment Variables

Key environment variables to configure:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key
DATABASE_PASSWORD=your-database-password
DJANGO_SECRET_KEY=your-secret-key

# Optional
DEBUG=True
PORTFOLIO_SCRAPING_BATCH_SIZE=10
RAG_SERVICE_URL=http://localhost:8001
```

### Database Setup

The application uses PostgreSQL with the pgvector extension:

```sql
-- Create database
CREATE DATABASE portfolio_db;

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

## 📊 Usage

### Web Interface

1. **Restaurant Discovery**
   - Browse restaurants by location, cuisine, or Michelin stars
   - View detailed restaurant profiles with menus and chef information
   - Search and filter functionality

2. **Intelligent Chat**
   - Ask questions about restaurants in natural language
   - Get personalized recommendations
   - Conversational search with context awareness

### API Usage

#### Restaurant Query API

```python
import requests

# Start conversation
response = requests.post("http://localhost:8001/conversation/start")
conversation_id = response.json()["conversation_id"]

# Query restaurants
response = requests.post(
    f"http://localhost:8001/conversation/{conversation_id}",
    json={"message": "Find me a Michelin starred Italian restaurant in Paris"}
)
```

#### Restaurant Search API

```python
# Search restaurants
response = requests.post(
    "http://localhost:8001/query",
    json={
        "query": "French restaurants with great wine selection",
        "limit": 10
    }
)
```

### Data Pipeline

#### Scraping Restaurants

```python
# Using Django management command
python manage.py scrape_restaurants --batch-size 10 --urls-file urls.txt

# Using Celery task
from restaurants.tasks import scrape_restaurants_task
scrape_restaurants_task.delay(job_id, urls_list)
```

#### Processing Data

```python
from data_pipeline.src.processors.data_processor import DataProcessor
from data_pipeline.src.scrapers.restaurant_scraper import RestaurantScraper

# Scrape restaurant
scraper = RestaurantScraper()
data = scraper.scrape_restaurant("https://restaurant-website.com")

# Process and save
processor = DataProcessor()
restaurant = processor.process_restaurant_data(data)
```

## 🔄 Data Flow

1. **Web Scraping**: Automated collection of restaurant data
2. **Data Processing**: Cleaning and structuring scraped data
3. **Database Storage**: Saving to PostgreSQL with Django ORM
4. **Embedding Generation**: Creating vector embeddings for search
5. **RAG Processing**: Intelligent query processing with context
6. **Response Generation**: AI-powered responses with source citations

## 🛡️ Security

### Authentication
- Django session authentication
- Token-based API authentication
- Admin interface protection

### Data Protection
- Environment variable management
- Secret key rotation
- Database connection security

### API Security
- CORS configuration
- Rate limiting (configurable)
- Input validation

## 🔍 Monitoring

### Application Monitoring
- Django admin interface
- Celery Flower for task monitoring
- Custom logging with structured logs

### Performance Monitoring
- Database query optimization
- Token usage tracking
- Response time monitoring

## 🧪 Testing

### Run Tests
```bash
# Django tests
cd django_app/src
python manage.py test

# RAG service tests
cd rag_service/src
pytest

# Integration tests
pytest tests/integration/
```

### Test Coverage
```bash
pytest --cov=src tests/
```

## 🚀 Deployment

### Production Deployment

1. **Set production environment variables**
```bash
DEBUG=False
ALLOWED_HOSTS=your-domain.com
# Set secure passwords and keys
```

2. **Use production Docker Compose**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

3. **Set up reverse proxy**
```bash
# Configure Nginx for SSL and load balancing
```

4. **Set up monitoring**
```bash
# Configure Sentry for error tracking
# Set up log aggregation
```

### Scaling

- **Horizontal scaling**: Multiple web/RAG service instances
- **Database optimization**: Read replicas, connection pooling
- **Caching**: Redis for session and query caching
- **Background processing**: Multiple Celery workers

## 📚 API Documentation

### Django REST API
- Swagger/OpenAPI documentation available at `/api/docs/`
- Restaurant CRUD operations
- User authentication endpoints

### RAG Service API
- FastAPI automatic documentation at `http://localhost:8001/docs`
- Conversation management
- Vector search endpoints

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔧 Troubleshooting

### Common Issues

1. **OpenAI API Errors**
   - Check API key validity
   - Monitor token usage
   - Verify rate limits

2. **Database Connection Issues**
   - Ensure PostgreSQL is running
   - Check connection parameters
   - Verify pgvector extension

3. **Redis Connection Issues**
   - Start Redis server
   - Check connection parameters
   - Verify Redis configuration

4. **Celery Issues**
   - Ensure Redis is running
   - Check worker logs
   - Verify task queue

### Debug Mode

Enable debug mode for detailed error information:
```bash
DEBUG=True
LOG_LEVEL=DEBUG
```

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the troubleshooting guide

## 🎯 Roadmap

### Upcoming Features
- [ ] Advanced filtering and sorting
- [ ] User reviews and ratings
- [ ] Restaurant recommendations ML model
- [ ] Mobile app API
- [ ] Multi-tenant support
- [ ] Advanced analytics dashboard

### Performance Improvements
- [ ] Query optimization
- [ ] Caching strategies
- [ ] Database indexing
- [ ] Background task optimization