"""
Safety guardrails for chat interactions.
Ensures conversations stay focused on restaurant and dining topics.
"""
import re
from typing import Dict, List, Tuple, Optional
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class RestaurantChatSafety:
    """
    Comprehensive safety validation for restaurant-focused chat.
    Implements multiple layers of content filtering and topic validation.
    """
    
    # Core restaurant and dining keywords
    RESTAURANT_KEYWORDS = {
        'establishments': ['restaurant', 'bistro', 'cafe', 'bar', 'gastropub', 'brasserie', 'tavern', 'eatery', 'diner'],
        'dining': ['dining', 'meal', 'lunch', 'dinner', 'breakfast', 'brunch', 'supper', 'feast'],
        'food': ['food', 'cuisine', 'dish', 'recipe', 'cooking', 'culinary', 'flavor', 'taste', 'ingredient'],
        'service': ['service', 'reservation', 'booking', 'waiter', 'server', 'hostess', 'sommelier'],
        'quality': ['michelin', 'star', 'starred', 'rating', 'review', 'quality', 'excellence', 'gourmet'],
        'experience': ['ambiance', 'atmosphere', 'experience', 'elegant', 'romantic', 'cozy', 'fine dining'],
        'beverages': ['wine', 'cocktail', 'drink', 'beverage', 'champagne', 'beer', 'spirits', 'sake'],
        'cuisine_types': ['italian', 'french', 'japanese', 'chinese', 'thai', 'indian', 'mexican', 'mediterranean'],
        'food_types': ['seafood', 'steakhouse', 'vegetarian', 'vegan', 'organic', 'farm to table', 'sushi'],
        'menu_items': ['appetizer', 'entree', 'dessert', 'course', 'tasting menu', 'prix fixe', 'special']
    }
    
    # Topics to explicitly block
    BLOCKED_TOPICS = {
        'politics': ['politics', 'political', 'election', 'government', 'president', 'congress', 'democrat', 'republican', 'voting', 'campaign'],
        'religion': ['religion', 'religious', 'church', 'bible', 'islam', 'christianity', 'judaism', 'buddhism', 'prayer', 'worship'],
        'violence': ['violence', 'violent', 'weapon', 'gun', 'bomb', 'terror', 'kill', 'murder', 'death', 'war', 'fight'],
        'inappropriate': ['sexual', 'sex', 'adult', 'explicit', 'nsfw', 'inappropriate', 'porn', 'nude'],
        'personal_info': ['password', 'ssn', 'social security', 'credit card', 'phone number', 'address', 'email'],
        'harmful': ['hack', 'illegal', 'drugs', 'suicide', 'self-harm', 'abuse', 'harassment'],
        'professional_advice': ['medical advice', 'legal advice', 'financial advice', 'investment', 'diagnosis', 'treatment', 'therapy']
    }
    
    # Polite decline messages for different scenarios
    DECLINE_MESSAGES = {
        'off_topic': [
            "I'm specialized in helping you discover amazing restaurants and dining experiences! Let's talk about Michelin-starred establishments, cuisine recommendations, or dining locations instead. What culinary adventure can I help you with?",
            "I'm your dedicated restaurant expert! I can help you find the perfect dining spot, explore cuisines, or learn about Michelin-starred restaurants. What dining experience are you looking for?",
            "Let's keep our conversation focused on the wonderful world of restaurants and dining! I can recommend cuisines, help you find great restaurants, or discuss culinary experiences. What would you like to explore?"
        ],
        'inappropriate': [
            "I maintain a professional focus on restaurant and dining topics. Please ask me about cuisines, restaurant recommendations, or dining experiences instead.",
            "I'm here to help with restaurant-related questions only. Let's discuss amazing dining experiences, menu recommendations, or culinary discoveries!",
            "I specialize in restaurants and culinary experiences. Please keep our conversation focused on dining, cuisines, and restaurant recommendations."
        ],
        'blocked_content': [
            "I can't discuss that topic, but I'd love to help you discover incredible restaurants! Ask me about Michelin-starred establishments, cuisine types, or dining recommendations.",
            "That's outside my area of expertise. I'm here to help with restaurant recommendations, menu suggestions, and culinary experiences. What dining adventure can I assist with?",
            "I focus exclusively on restaurant and dining topics. Let's explore amazing cuisines, find great restaurants, or discuss culinary experiences instead!"
        ],
        'rate_limit': [
            "Please slow down a bit! I want to provide you with thoughtful restaurant recommendations. Let's take our time to explore the perfect dining options for you.",
            "I appreciate your enthusiasm! Let's take a moment to discuss your dining preferences so I can give you the best restaurant recommendations.",
            "Let's pace our conversation so I can provide you with the most helpful restaurant insights and recommendations."
        ]
    }
    
    # Common conversational words that are acceptable
    ACCEPTABLE_CONVERSATIONAL_WORDS = {
        'greetings': ['hello', 'hi', 'hey', 'good morning', 'good evening', 'greetings'],
        'courtesy': ['please', 'thank you', 'thanks', 'sorry', 'excuse me'],
        'questions': ['what', 'where', 'when', 'how', 'why', 'which', 'who', 'can', 'could', 'would'],
        'requests': ['help', 'recommend', 'suggest', 'find', 'show', 'tell', 'explain', 'describe'],
        'descriptors': ['best', 'good', 'great', 'amazing', 'excellent', 'top', 'popular', 'famous'],
        'locations': ['near', 'in', 'at', 'around', 'city', 'area', 'location', 'place', 'neighborhood']
    }
    
    def __init__(self):
        """Initialize the safety validator."""
        self.max_message_length = getattr(settings, 'CHAT_MAX_MESSAGE_LENGTH', 1000)
        self.rate_limit_messages = getattr(settings, 'CHAT_RATE_LIMIT_MESSAGES', 20)
        self.rate_limit_window = getattr(settings, 'CHAT_RATE_LIMIT_WINDOW', 60)  # seconds
    
    def validate_message(self, message: str, user_id: Optional[str] = None) -> Dict[str, any]:
        """
        Comprehensive message validation.
        
        Args:
            message: The user's message to validate
            user_id: Optional user identifier for rate limiting
            
        Returns:
            Dict with validation results and any error messages
        """
        # Basic sanitization
        cleaned_message = self._sanitize_input(message)
        
        # Length validation
        if len(cleaned_message) > self.max_message_length:
            return {
                'valid': False,
                'reason': f"Please keep your message under {self.max_message_length} characters. I'm here to help with restaurant-related questions!",
                'category': 'length_limit'
            }
        
        # Empty message check
        if not cleaned_message.strip():
            return {
                'valid': False,
                'reason': "Please send a message! I'm here to help you discover amazing restaurants and dining experiences.",
                'category': 'empty_message'
            }
        
        # Check for blocked content
        blocked_check = self._check_blocked_content(cleaned_message)
        if not blocked_check['valid']:
            return blocked_check
        
        # Check if message is restaurant-related
        topic_check = self._validate_restaurant_topic(cleaned_message)
        if not topic_check['valid']:
            return topic_check
        
        # All checks passed
        return {
            'valid': True,
            'cleaned_message': cleaned_message
        }
    
    def _sanitize_input(self, message: str) -> str:
        """
        Sanitize user input to prevent XSS and other attacks.
        
        Args:
            message: Raw user input
            
        Returns:
            Sanitized message
        """
        if not message:
            return ""
        
        # Remove script tags and potential XSS
        message = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', message, flags=re.IGNORECASE)
        message = re.sub(r'<[^>]*>', '', message)  # Remove HTML tags
        message = re.sub(r'javascript:', '', message, flags=re.IGNORECASE)
        message = re.sub(r'on\w+\s*=', '', message, flags=re.IGNORECASE)
        
        # Remove excessive whitespace
        message = re.sub(r'\s+', ' ', message).strip()
        
        return message
    
    def _check_blocked_content(self, message: str) -> Dict[str, any]:
        """
        Check if message contains blocked content.
        
        Args:
            message: Cleaned message to check
            
        Returns:
            Validation result
        """
        message_lower = message.lower()
        
        for category, terms in self.BLOCKED_TOPICS.items():
            for term in terms:
                if term.lower() in message_lower:
                    logger.warning(f"Blocked content detected: {term} in category {category}")
                    return {
                        'valid': False,
                        'reason': self._get_random_decline_message('blocked_content'),
                        'category': f'blocked_{category}'
                    }
        
        return {'valid': True}
    
    def _validate_restaurant_topic(self, message: str) -> Dict[str, any]:
        """
        Validate that the message is related to restaurants and dining.
        
        Args:
            message: Cleaned message to validate
            
        Returns:
            Validation result
        """
        message_lower = message.lower()
        
        # Check for restaurant-related keywords
        has_restaurant_keyword = any(
            keyword.lower() in message_lower
            for category in self.RESTAURANT_KEYWORDS.values()
            for keyword in category
        )
        
        # Check for acceptable conversational words
        has_conversational_word = any(
            word.lower() in message_lower
            for category in self.ACCEPTABLE_CONVERSATIONAL_WORDS.values()
            for word in category
        )
        
        # Allow short messages that might be greetings or brief questions
        is_short_message = len(message_lower.split()) <= 5
        
        # Allow if it has restaurant keywords, conversational words, or is a short message
        if has_restaurant_keyword or (has_conversational_word and is_short_message):
            return {'valid': True}
        
        # For longer messages without restaurant context, decline politely
        if len(message_lower.split()) > 5:
            return {
                'valid': False,
                'reason': self._get_random_decline_message('off_topic'),
                'category': 'off_topic'
            }
        
        return {'valid': True}
    
    def _get_random_decline_message(self, message_type: str) -> str:
        """
        Get a random polite decline message.
        
        Args:
            message_type: Type of decline message needed
            
        Returns:
            Random decline message
        """
        import random
        messages = self.DECLINE_MESSAGES.get(message_type, self.DECLINE_MESSAGES['off_topic'])
        return random.choice(messages)
    
    def get_safety_guidelines(self) -> Dict[str, any]:
        """
        Get safety guidelines for display to users.
        
        Returns:
            Dictionary with safety guidelines and examples
        """
        return {
            'title': '🍽️ Your Restaurant Assistant Guidelines',
            'description': "I'm specialized in restaurants, dining, and culinary experiences. I can help with Michelin-starred establishments, cuisine recommendations, menu suggestions, and dining locations worldwide.",
            'focus': "Please keep our conversation focused on food and dining topics!",
            'examples': [
                "Ask about Michelin-starred restaurants in specific cities",
                "Get cuisine recommendations and menu suggestions",
                "Discover restaurants with specific ambiance or dietary options",
                "Learn about chef specialties and wine pairings",
                "Find dining options for special occasions"
            ],
            'boundaries': "I focus exclusively on restaurant and culinary topics to provide you with the best dining recommendations and experiences."
        }


# Global safety instance
chat_safety = RestaurantChatSafety()