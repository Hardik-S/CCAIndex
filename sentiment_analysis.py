import os
import requests
import json
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Download NLTK data (run once)
nltk.download('vader_lexicon', quiet=True)

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Companies configuration
companies = [
    {
        "name": "Apple Inc",
        "search_terms": ["Apple sustainability", "Apple environmental"],
        "metrics": {
            "emissions_reduction": 0.85,
            "renewable_energy": 0.92,
            "water_conservation": 0.78,
            "waste_management": 0.88,
            "supply_chain": 0.76
        }
    },
    {
        "name": "Microsoft Corporation",
        "search_terms": ["Microsoft carbon negative", "Microsoft sustainability"],
        "metrics": {
            "emissions_reduction": 0.90,
            "renewable_energy": 0.95,
            "water_conservation": 0.82,
            "waste_management": 0.89,
            "supply_chain": 0.84
        }
    }
]

# Weights for different metrics
weights = {
    "emissions_reduction": 0.25,
    "renewable_energy": 0.25,
    "water_conservation": 0.15,
    "waste_management": 0.15,
    "supply_chain": 0.20,
    "sentiment_weight": 0.25
}

def get_company_news(company_name, search_terms, months=5):
    """Fetch news about a company from multiple sources"""
    all_articles = []
    
    # Retrieve API keys from environment variables
    newsapi_key = os.getenv('NEWSAPI_KEY')
    gnews_key = os.getenv('GNEWS_KEY')
    
    if not (newsapi_key and gnews_key):
        raise ValueError("Missing API keys. Check your .env file.")
    
    for term in search_terms:
        for i in range(months):
            # Calculate date range
            end_date = datetime.now() - timedelta(days=i*30)
            start_date = end_date - timedelta(days=30)
            
            # Format dates for API
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")
            month_name = end_date.strftime("%b")
            
            # NewsAPI
            try:
                newsapi_url = f"https://newsapi.org/v2/everything?q={term}&from={from_date}&to={to_date}&sortBy=popularity&apiKey={newsapi_key}"
                newsapi_response = requests.get(newsapi_url)
                newsapi_data = newsapi_response.json()
                
                if newsapi_data.get("status") == "ok":
                    for article in newsapi_data.get("articles", [])[:5]:
                        article["month"] = month_name
                        article["source"] = "NewsAPI"
                        all_articles.append(article)
            except Exception as e:
                print(f"NewsAPI error for {term}: {e}")
            
            # GNews
            try:
                gnews_url = f"https://gnews.io/api/v4/search?q={term}&from={from_date}&to={to_date}&token={gnews_key}&max=5"
                gnews_response = requests.get(gnews_url)
                gnews_data = gnews_response.json()
                
                if gnews_data.get("articles"):
                    for article in gnews_data["articles"]:
                        standardized_article = {
                            "title": article.get("title", ""),
                            "description": article.get("description", ""),
                            "url": article.get("url", ""),
                            "month": month_name,
                            "source": "GNews"
                        }
                        all_articles.append(standardized_article)
            except Exception as e:
                print(f"GNews error for {term}: {e}")
    
    return all_articles

def analyze_sentiment(articles):
    """Analyze sentiment of articles using VADER"""
    if not articles:
        return {"score": 0, "trend": [0, 0, 0, 0, 0], "months": ["May", "Jun", "Jul", "Aug", "Sep"]}
    
    # Calculate overall sentiment
    sentiments = []
    for article in articles:
        content = article.get("title", "") + " " + article.get("description", "")
        sentiment = sia.polarity_scores(content)
        sentiments.append(sentiment["compound"])
    
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
    
    # Monthly sentiment trend
    months = ["May", "Jun", "Jul", "Aug", "Sep"]
    monthly_sentiments = {month: [] for month in months}
    
    for article in articles:
        month = article.get("month")
        if month in monthly_sentiments:
            content = article.get("title", "") + " " + article.get("description", "")
            sentiment = sia.polarity_scores(content)
            monthly_sentiments[month].append(sentiment["compound"])
    
    # Calculate average sentiment per month
    trend = []
    for month in months:
        scores = monthly_sentiments[month]
        avg = sum(scores) / len(scores) if scores else 0
        trend.append(avg)
    
    # Ensure 5 data points
    while len(trend) < 5:
        trend.append(0)
    
    return {
        "score": avg_sentiment,
        "trend": trend,
        "months": months
    }

def calculate_scores():
    """Calculate climate adaptability scores for companies"""
    results = []
    for company in companies:
        # Get news articles
        articles = get_company_news(company["name"], company["search_terms"])
        
        # Analyze sentiment
        company["sentiment"] = analyze_sentiment(articles)
        
        # Calculate ESG score
        esg_score = sum(value * weights[metric] for metric, value in company["metrics"].items())
        company["esg_score"] = round(esg_score * 100)
        
        # Convert sentiment from -1 to +1 scale to 0-100
        sentiment_score = round((company["sentiment"]["score"] + 1) / 2 * 100)
        company["sentiment_score"] = sentiment_score
        
        # Calculate overall score
        sentiment_weight = weights["sentiment_weight"]
        esg_weight = 1 - sentiment_weight
        company["overall_score"] = round(company["esg_score"] * esg_weight + sentiment_score * sentiment_weight)
        
        results.append(company)
    
    # Sort by overall score
    results.sort(key=lambda x: x["overall_score"], reverse=True)
    return results

def save_data():
    """Calculate and save scores to JSON"""
    data = calculate_scores()
    
    with open('climate_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Data saved for {len(data)} companies")
    return data

# Create .env file instructions
def create_env_file():
    """Generate .env file template"""
    env_content = """# News API Credentials
NEWSAPI_KEY=your_newsapi_key_here
GNEWS_KEY=your_gnews_key_here
"""
    with open('.env', 'w') as f:
        f.write(env_content)
    print("Created .env file template. Please replace with your actual API keys.")

if __name__ == "__main__":
    # Uncomment to create .env file template
    # create_env_file()
    save_data()