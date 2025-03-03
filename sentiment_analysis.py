# sentiment_analysis.py
import requests
import pandas as pd
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import json
import os
from datetime import datetime, timedelta

# Download NLTK data (run once)
nltk.download('vader_lexicon')

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# News API key
NEWS_API_KEY = "f3d8d90a61af4757a0c86708315d463e"

# Sample companies and their ESG data (in a real app, this would be scraped from ESG reports)
companies = [
    {
        "name": "EcoTech Solutions",
        "metrics": {
            "emissions_reduction": 0.85,
            "renewable_energy": 0.92,
            "water_conservation": 0.78,
            "waste_management": 0.88,
            "supply_chain": 0.76
        },
        "search_terms": ["EcoTech Solutions", "EcoTech sustainability"]
    },
    {
        "name": "GreenPower Inc",
        "metrics": {
            "emissions_reduction": 0.76,
            "renewable_energy": 0.95,
            "water_conservation": 0.65,
            "waste_management": 0.71,
            "supply_chain": 0.80
        },
        "search_terms": ["GreenPower Inc", "GreenPower renewable"]
    },
    {
        "name": "SustainCorp",
        "metrics": {
            "emissions_reduction": 0.92,
            "renewable_energy": 0.78,
            "water_conservation": 0.82,
            "waste_management": 0.79,
            "supply_chain": 0.85
        },
        "search_terms": ["SustainCorp", "SustainCorp climate"]
    },
    {
        "name": "FutureFriendly Ltd",
        "metrics": {
            "emissions_reduction": 0.67,
            "renewable_energy": 0.71,
            "water_conservation": 0.73,
            "waste_management": 0.68,
            "supply_chain": 0.72
        },
        "search_terms": ["FutureFriendly", "FutureFriendly sustainable"]
    },
    {
        "name": "ClimateWise",
        "metrics": {
            "emissions_reduction": 0.80,
            "renewable_energy": 0.83,
            "water_conservation": 0.77,
            "waste_management": 0.75,
            "supply_chain": 0.79
        },
        "search_terms": ["ClimateWise", "ClimateWise environment"]
    }
]

# Weights for different metrics
weights = {
    "emissions_reduction": 0.25,
    "renewable_energy": 0.25,
    "water_conservation": 0.15,
    "waste_management": 0.15,
    "supply_chain": 0.20,
    "sentiment_weight": 0.25  # Weight for sentiment in overall score
}

def get_company_news(company_name, search_terms, months=5):
    """Fetch news about a company from the News API"""
    all_articles = []
    
    # Get data for the last few months
    for i in range(months):
        # Calculate date range
        end_date = datetime.now() - timedelta(days=i*30)
        start_date = end_date - timedelta(days=30)
        
        # Format dates for API
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")
        
        # Fetch articles for each search term
        for term in search_terms:
            try:
                url = f"https://newsapi.org/v2/everything?q={term}&from={from_date}&to={to_date}&sortBy=popularity&apiKey={NEWS_API_KEY}"
                response = requests.get(url)
                data = response.json()
                
                if data.get("status") == "ok" and data.get("articles"):
                    # Store articles with the month
                    month_name = end_date.strftime("%b")
                    for article in data["articles"][:10]:  # Limit to top 10 articles
                        article["month"] = month_name
                        all_articles.append(article)
            except Exception as e:
                print(f"Error fetching news for {term}: {e}")
    
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
        sentiments.append(sentiment["compound"])  # Compound score ranges from -1 to 1
    
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
    
    # Calculate monthly sentiment trends
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
    
    # Ensure we have 5 data points
    while len(trend) < 5:
        trend.append(0)
    
    return {
        "score": avg_sentiment,
        "trend": trend,
        "months": months
    }

def calculate_scores():
    """Calculate climate adaptability scores for all companies"""
    for company in companies:
        # Get news articles
        articles = get_company_news(company["name"], company["search_terms"])
        
        # Analyze sentiment
        company["sentiment"] = analyze_sentiment(articles)
        
        # Calculate ESG score
        esg_score = 0
        for metric, value in company["metrics"].items():
            esg_score += value * weights[metric]
        
        # Normalize scores to 0-100 scale
        company["esg_score"] = round(esg_score * 100)
        
        # Convert sentiment from -1 to +1 scale to 0-100
        sentiment_score = round((company["sentiment"]["score"] + 1) / 2 * 100)
        company["sentiment_score"] = sentiment_score
        
        # Calculate overall score
        sentiment_weight = weights["sentiment_weight"]
        esg_weight = 1 - sentiment_weight
        company["overall_score"] = round(company["esg_score"] * esg_weight + sentiment_score * sentiment_weight)
    
    # Sort companies by overall score
    companies.sort(key=lambda x: x["overall_score"], reverse=True)
    
    return {
        "companies": companies,
        "weights": weights
    }

def save_data():
    """Calculate scores and save to a JSON file"""
    data = calculate_scores()
    
    # Save to file
    with open('climate_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Data saved for {len(data['companies'])} companies")
    return data

if __name__ == "__main__":
    save_data()