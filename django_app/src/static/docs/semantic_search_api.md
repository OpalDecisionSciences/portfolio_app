# Semantic Search API Documentation

## Overview

The Semantic Search API provides AI-powered restaurant discovery with intelligent query routing and natural language understanding. It complements existing traditional search by adding semantic analysis, intent detection, and hybrid search capabilities.

## Base URL
```
https://opaldecisionsciences.com/restaurants/api/
```

## Authentication
All endpoints use Django CSRF protection. Include the CSRF token in requests:
```javascript
headers: {
    'X-CSRFToken': getCSRFToken(),
    'Content-Type': 'application/json'
}
```

---

## Endpoints

### 1. Semantic Search
**Endpoint:** `POST /semantic-search/`  
**Alternative:** `GET /semantic-search/`

Advanced semantic search with intelligent query routing based on complexity analysis.

#### Request Body (POST)
```json
{
    "query": "romantic dinner for anniversary",
    "context": {
        "location": "Paris",
        "user_preferences": {
            "price_range": "$$",
            "dietary_restrictions": ["vegetarian"]
        },
        "address": "123 Main St, Paris"
    },
    "filters": {
        "city": "Paris",
        "country": "France",
        "cuisine_type": "French",
        "michelin_stars": [1, 2, 3],
        "price_range": ["$$", "$$$"],
        "rating_min": 4.0,
        "rating_max": 5.0
    },
    "limit": 20,
    "force_method": "semantic"
}
```

#### Query Parameters (GET)
```
?query=romantic dinner
&city=Paris
&cuisine_type=French
&limit=10
&force_method=hybrid
```

#### Response
```json
{
    "results": [
        {
            "id": "uuid-string",
            "name": "Le Jules Verne",
            "slug": "le-jules-verne",
            "city": "Paris",
            "country": "France",
            "cuisine_type": "French",
            "michelin_stars": 1,
            "rating": 4.8,
            "price_range": "$$$",
            "description": "Elegant Michelin-starred restaurant...",
            "url": "/restaurants/le-jules-verne/",
            "featured_image": "https://...",
            "relevance_score": 0.95,
            "semantic_score": 0.88,
            "traditional_score": 0.72,
            "explanation": "Perfect for romantic occasions with intimate atmosphere...",
            "matched_features": ["romantic", "fine-dining", "anniversary"]
        }
    ],
    "total_count": 15,
    "search_method": "semantic",
    "intent_analysis": {
        "type": "experience",
        "complexity": 0.8,
        "entities": {
            "experience": "romantic",
            "occasion": "anniversary"
        },
        "sentiment": "positive"
    },
    "response_time_ms": 245.8,
    "semantic_enhanced": true,
    "api_version": "semantic_v1",
    "enhanced_scoring": true
}
```

#### Search Methods
- `automatic` (default): System selects optimal method based on query analysis
- `semantic`: Pure AI-powered semantic search
- `hybrid`: Combines traditional and semantic approaches
- `traditional`: Enhanced traditional search with intent optimization
- `geographic`: Location-aware semantic search

---

### 2. Query Intent Analysis
**Endpoint:** `GET /semantic-search/intent/`

Analyzes search query intent and recommends optimal search method.

#### Query Parameters
```
?query=best family friendly restaurants
&location=New York
&user_type=authenticated
```

#### Response
```json
{
    "intent_analysis": {
        "original_query": "best family friendly restaurants",
        "intent_type": "experience",
        "entities": {
            "experience": "family-friendly",
            "quality": "best"
        },
        "sentiment": "positive",
        "complexity_score": 0.6,
        "recommended_method": "hybrid",
        "analysis_confidence": "high",
        "routing_explanation": "Query classified as experience with 60% complexity"
    },
    "api_version": "intent_v1",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Intent Types
- `location`: Location-based queries
- `cuisine`: Cuisine-specific searches
- `experience`: Experience or atmosphere queries
- `specific`: Simple, specific restaurant searches
- `general`: General discovery queries

---

### 3. Hybrid Search
**Endpoint:** `POST /hybrid-search/`

Forces hybrid search combining traditional and semantic approaches with intelligent weighting.

#### Request Body
```json
{
    "query": "innovative modern cuisine",
    "context": {
        "location": "Tokyo",
        "user_preferences": {
            "experience_level": "adventurous"
        },
        "search_history": ["sushi", "omakase", "modern japanese"]
    },
    "city": "Tokyo",
    "limit": 15
}
```

#### Response
```json
{
    "results": [/* Restaurant objects */],
    "total_count": 12,
    "traditional_count": 8,
    "semantic_count": 6,
    "search_method": "hybrid",
    "source": "hybrid",
    "api_version": "hybrid_v1",
    "scoring_explanation": "Results combine traditional search relevance with semantic understanding",
    "response_time_ms": 180.5
}
```

---

### 4. Search Methods Information
**Endpoint:** `GET /search/methods/`

Returns available search methods and their characteristics.

#### Response
```json
{
    "search_methods": {
        "traditional": {
            "name": "Traditional Search",
            "description": "Fast keyword-based search with PostgreSQL full-text search",
            "best_for": ["Simple queries", "Exact matches", "Fast results"],
            "performance": "High speed, low latency"
        },
        "semantic": {
            "name": "Semantic Search",
            "description": "AI-powered semantic understanding using RAG service",
            "best_for": ["Complex queries", "Conceptual search", "Experience-based queries"],
            "performance": "Moderate speed, high relevance"
        },
        "hybrid": {
            "name": "Hybrid Search",
            "description": "Combines traditional and semantic search with intelligent weighting",
            "best_for": ["Most queries", "Balanced performance", "High accuracy"],
            "performance": "Balanced speed and relevance"
        },
        "geographic": {
            "name": "Geographic Search",
            "description": "Location-aware search with semantic enhancement",
            "best_for": ["Location queries", "Near me searches", "Geographic filtering"],
            "performance": "Location-optimized results"
        }
    },
    "default_method": "automatic_routing",
    "api_version": "methods_v1",
    "routing_info": {
        "automatic": "System automatically selects best method based on query analysis",
        "manual": "Force specific method using force_method parameter"
    }
}
```

---

## Error Handling

### Error Response Format
```json
{
    "error": "Error description",
    "details": "Detailed error message",
    "fallback_available": true,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common HTTP Status Codes
- `200 OK`: Success
- `400 Bad Request`: Invalid query or parameters
- `500 Internal Server Error`: Server error with fallback available
- `502 Bad Gateway`: RAG service unavailable
- `503 Service Unavailable`: Search service temporarily unavailable

---

## Integration Examples

### JavaScript Frontend Integration
```javascript
async function semanticSearch(query, options = {}) {
    const response = await fetch('/restaurants/api/semantic-search/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            query: query,
            limit: options.limit || 20,
            force_method: options.method || 'automatic',
            ...options.filters
        })
    });
    
    if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
    }
    
    return await response.json();
}

// Example usage
try {
    const results = await semanticSearch('romantic dinner for anniversary', {
        method: 'hybrid',
        filters: { city: 'Paris', michelin_stars: [1, 2] }
    });
    
    console.log(`Found ${results.total_count} restaurants`);
    console.log(`Search method: ${results.search_method}`);
    console.log(`Response time: ${results.response_time_ms}ms`);
    
    results.results.forEach(restaurant => {
        console.log(`${restaurant.name}: ${restaurant.explanation}`);
    });
} catch (error) {
    console.error('Search error:', error);
}
```

### Python Backend Integration
```python
import requests
import json

def semantic_search_restaurants(query, **kwargs):
    """Perform semantic search using the API."""
    url = 'http://localhost:8000/restaurants/api/semantic-search/'
    
    data = {
        'query': query,
        'limit': kwargs.get('limit', 20),
        **kwargs
    }
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    
    return response.json()

# Example usage
results = semantic_search_restaurants(
    'cozy atmosphere with great wine',
    city='Rome',
    price_range=['$$', '$$$'],
    force_method='hybrid'
)

print(f"Found {results['total_count']} restaurants")
for restaurant in results['results']:
    print(f"{restaurant['name']}: {restaurant.get('explanation', 'No explanation')}")
```

---

## Performance Considerations

### Caching
- Search results are cached in Redis for 30 minutes
- Intent analysis cached for 1 hour
- Restaurant data cached for 2 hours

### Rate Limiting
- 100 requests per minute per IP for authenticated users
- 50 requests per minute per IP for anonymous users

### Query Optimization Tips
1. Use specific queries for better semantic understanding
2. Include context when available (location, preferences)
3. Use appropriate search method for query type
4. Leverage intent analysis for query preprocessing

---

## Monitoring and Analytics

### Search Metrics Available
- Query complexity distribution
- Search method usage statistics
- Response time percentiles
- Success/error rates
- Cache hit rates

### Performance Targets
- 95% of queries complete under 500ms
- 99.9% uptime with fallback mechanisms
- Cache hit rate above 75%

---

## Migration from Traditional Search

### Backward Compatibility
All existing search APIs remain fully functional. Semantic search is additive.

### Gradual Migration Strategy
1. **Phase 1**: Use semantic search for complex queries only
2. **Phase 2**: Implement hybrid search as default
3. **Phase 3**: Route all queries through semantic analysis

### A/B Testing Support
Use `force_method` parameter to test different search approaches:
```javascript
// Traditional search
semanticSearch(query, { force_method: 'traditional' })

// Semantic search
semanticSearch(query, { force_method: 'semantic' })

// Hybrid approach
semanticSearch(query, { force_method: 'hybrid' })
```

---

## Troubleshooting

### Common Issues

**Query returns no results:**
- Check query complexity and try different search methods
- Verify filters are not too restrictive
- Use intent analysis to understand query routing

**Slow response times:**
- Check if RAG service is responding
- Monitor cache hit rates
- Consider using traditional search for simple queries

**Semantic scoring seems inaccurate:**
- Ensure RAG service is properly trained
- Check if query context is provided
- Consider hybrid search for better balance

### Debug Endpoints
- `GET /restaurants/api/cache/health/`: Check cache system health
- `GET /restaurants/api/cache/stats/`: Get cache performance metrics
- `GET /restaurants/api/search/methods/`: Verify available search methods

---

## Changelog

### Version 1.0.0 (2024-01-15)
- Initial release of semantic search API
- Intent analysis and query routing
- Hybrid search implementation
- Full backward compatibility

### Planned Features
- Multi-language query support
- Enhanced entity extraction
- Personalized semantic search
- Voice query optimization