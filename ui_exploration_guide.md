# 🍽️ Restaurant Application UI Exploration Guide

## 🌐 Access the Application
**Base URL**: http://localhost:8000

---

## 📄 **Main Pages to Explore**

### 1. **Homepage** - http://localhost:8000/
**Features to Test:**
- Global restaurant search with live suggestions
- AI-powered recommendations section
- Featured restaurants showcase
- Search functionality with location filtering
- Global features highlighting (15,000+ restaurants, AI analysis, timezones)

**What to Look For:**
- Search autocomplete with restaurant images
- Michelin star displays
- Real-time location-based filtering
- Responsive design elements

---

### 2. **Restaurant List** - http://localhost:8000/restaurants/
**Features to Test:**
- Advanced filtering sidebar:
  - Country selection (48 countries available)
  - City selection (5,813 cities available) 
  - Cuisine type filtering (1,700+ cuisine types)
  - Michelin stars filter (1, 2, 3 stars)
  - Price range filtering ($, $$, $$$, $$$$)
  - Sorting options (name, rating, stars, city)
- Pagination for large datasets
- Restaurant cards with images and details

**What to Look For:**
- Filter combinations work together
- Restaurant cards show Michelin stars with ⭐ icons
- Image galleries with "+X more" badges
- Location and cuisine information
- Proper pagination controls

---

### 3. **Restaurant Detail Pages**
**Sample URLs to Test:**
- http://localhost:8000/restaurants/hisa-franko-kobarid/ (Slovenia, 3 Michelin stars)
- http://localhost:8000/restaurants/tresind-studio-dubai/ (Dubai, Indian cuisine)
- http://localhost:8000/restaurants/boury-roeselare/ (Belgium, fine dining)

**Features to Test:**
- Image galleries with AI categorization
- Comprehensive restaurant information
- Real-time timezone display for global restaurants
- Menu sections and items (when available)
- Chef and ownership information
- Atmosphere and ambiance descriptions
- Contact information and hours

**What to Look For:**
- AI-categorized images (menu_item, scenery_ambiance, etc.)
- Global timezone support showing local time
- LLM-analyzed content display
- Responsive image galleries
- Structured menu presentation

---

## 🔍 **Advanced Search & Filtering**

### Search Examples to Try:
- **By Cuisine**: "French", "Italian", "Japanese", "Indian"
- **By Location**: "Paris", "Dubai", "Tokyo", "New York"
- **By Restaurant Name**: "Hiša Franko", "Trèsind", "Boury"
- **By Features**: "Michelin", "stars", "fine dining"

### Filter Combinations to Test:
- Country: France + Cuisine: French + Stars: 3
- Country: Japan + Price: $$$$ 
- Cuisine: Italian + City: specific cities
- Stars: 2 + Sort by: Rating

---

## 🔌 **API Endpoints to Test**

### 1. **Search API**
```
http://localhost:8000/restaurants/api/search/?q=french&max_results=5
http://localhost:8000/restaurants/api/search/?q=michelin&location=paris
```

### 2. **Recommendations API**
```
http://localhost:8000/restaurants/api/recommendations/?max_results=6
```

### 3. **Stats API**
```
http://localhost:8000/restaurants/api/stats/
```

### 4. **Restaurant Images API**
```
http://localhost:8000/restaurants/api/[restaurant-id]/images/
```

---

## 🧪 **Testing Scenarios**

### Scenario 1: **Global Restaurant Discovery**
1. Go to homepage
2. Search for "Dubai restaurants"
3. Filter by 3 Michelin stars
4. Click on a restaurant detail page
5. Check timezone information and images

### Scenario 2: **Cuisine Exploration**  
1. Go to restaurant list
2. Filter by Cuisine: "French"
3. Filter by Country: "France"
4. Sort by Michelin stars
5. Explore multiple restaurant details

### Scenario 3: **Mobile-Responsive Testing**
1. Resize browser window to mobile size
2. Test search functionality
3. Check filter sidebar behavior
4. Verify image galleries work on mobile
5. Test restaurant detail page layout

### Scenario 4: **Data Quality Verification**
1. Check recently scraped restaurants
2. Verify images display correctly
3. Check timezone information accuracy
4. Verify LLM-analyzed content quality
5. Test menu structure display

---

## 📊 **Recently Scraped Restaurants to Explore**

Based on current database, here are freshly scraped restaurants with complete data:

1. **Hiša Franko** (Slovenia)
   - URL: `/restaurants/hisa-franko-kobarid/`
   - Features: 4 images, complete LLM analysis, Slovenian → English translation

2. **Trèsind Studio** (Dubai)
   - URL: `/restaurants/tresind-studio-dubai/`
   - Features: Indian cuisine, Dubai location, comprehensive content

3. **Boury** (Belgium)
   - URL: `/restaurants/boury-roeselare/`
   - Features: Fine dining, Belgium location, detailed atmosphere info

4. **FZN by Björn Frantzén** (Dubai)
   - URL: `/restaurants/fzn-by-bjorn-frantzen-atlantis-the-palm/`
   - Features: Celebrity chef, Dubai location, luxury dining

5. **Zilte** (Belgium)
   - URL: `/restaurants/zilte-antwerpen/`
   - Features: Antwerp location, Belgian cuisine

---

## 🎯 **Key Features to Highlight**

### ✨ **AI-Powered Features**
- **Smart Search**: Autocomplete with relevance scoring
- **Content Analysis**: LLM-extracted cuisine, ambiance, chef info
- **Image Categorization**: AI-classified images (menu, ambiance, food)
- **Translation Support**: Multilingual content automatically translated

### 🌍 **Global Features**
- **Timezone Support**: Real-time local time for restaurants worldwide
- **Multi-Country Coverage**: 48 countries represented
- **Cultural Diversity**: 1,700+ cuisine types from around the world

### 📱 **User Experience**
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Fast Search**: Real-time autocomplete and filtering
- **Rich Media**: High-quality images with proper attribution
- **Detailed Information**: Comprehensive restaurant profiles

---

## 🚀 **Getting Started**

1. **Open**: http://localhost:8000
2. **Start with**: Homepage search for "Michelin stars"
3. **Explore**: Filter results by your preferred cuisine
4. **Deep dive**: Click on a restaurant for full details
5. **Compare**: Use the restaurant list to compare multiple venues

---

## 📈 **Live Data Updates**

The application is actively scraping new restaurants in the background. You can see:
- Recently added restaurants in the list
- Fresh content with comprehensive LLM analysis
- New images being categorized and displayed
- Growing database of global restaurants

**Monitor Progress**: Check restaurant list page and look for recently added timestamps!