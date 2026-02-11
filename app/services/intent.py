import json
# from openai import AsyncOpenAI
import google.generativeai as genai
from loguru import logger
from app.core.config import settings

class IntentService:
    def __init__(self):
        # self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def parse_user_query(self, query: str) -> dict:
        """
        Parses user's natural language query into structured search parameters.
        Cost: Extremely low (using gpt-4o-mini).
        """
        logger.info(f"🧠 User intent analysis: '{query}'")
        
        prompt = f"""
        Analyze the following user search query: "{query}"
        
        Your task is to extract structural information for a price monitoring system.
        
        RULES:
        1. "search_term": A concise, optimized string for a search engine (e.g. "iPhone 16 128GB Black").
        2. "category": One of [Electronics, Shoes, Clothing, Home, Other].
        3. "brand": The primary brand (e.g. "Apple", "Nike").
        4. "forbidden_keywords": List of words that indicate an accessory or wrong item (e.g. ["case", "cover", "glass", "cable", "strap"]).
        5. "max_price": Integer or null if not specified.

        RETURN JSON ONLY.
        """

        try:
            # response = await self.client.chat.completions.create(
            #     model="gpt-4o-mini",
            #     messages=[
            #         {"role": "system", "content": "You are a helpful assistant that converts human queries into structured JSON search data."},
            #         {"role": "user", "content": prompt}
            #     ],
            #     response_format={"type": "json_object"}
            # )
            # data = json.loads(response.choices[0].message.content)

            generation_config = genai.GenerationConfig(response_mime_type="application/json")
            response = await self.model.generate_content_async(prompt, generation_config=generation_config)
            cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(cleaned_text)
            logger.success(f"🎯 Intent defined: {data['search_term']} ({data['category']})")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error parsing intent: {e}")
            # Fallback if AI fails
            return {
                "search_term": query,
                "category": "Other",
                "max_price": None,
                "raw_query": query
            }

intent_service = IntentService()
