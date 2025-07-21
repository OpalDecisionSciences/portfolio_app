"""
FastAPI application for RAG service.
"""
import os
import sys
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional
from pathlib import Path

import redis
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from langchain_postgres import PGVector
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
import openai

# Get OpenAI API Key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Get API key from environment variable
api_key = os.getenv("OPENAI_API_KEY")

# API Key validation
if api_key and api_key.startswith('sk-proj-') and len(api_key) > 10:
    print("API key looks good.")
else:
    print("There might be a problem with your API key. Please check!")

# Setup portfolio paths for cross-component imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "shared" / "src"))
from config import setup_portfolio_paths
setup_portfolio_paths()

from token_management.token_manager import init_token_manager, call_openai_chat, get_token_usage_summary

load_dotenv(find_dotenv())

# Database configuration - Using Django-compatible environment variables
# Support both Django naming (DATABASE_*) and legacy Docker naming (POSTGRES_*) for compatibility
db_user = os.getenv("DATABASE_USER") or os.getenv("POSTGRES_USER", "postgres")
db_password = os.getenv("DATABASE_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "password")
db_host = os.getenv("DATABASE_HOST", "db")
db_port = os.getenv("DATABASE_PORT", "5432")
db_name = os.getenv("DATABASE_NAME") or os.getenv("POSTGRES_DB", "restaurants_db")

CONNECTION_STRING = (
    f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize token manager
TOKEN_DIR = Path(__file__).parent.parent.parent.parent / "shared" / "token_management"
init_token_manager(TOKEN_DIR)


class Question(BaseModel):
    question: str
    context: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ConversationRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class RestaurantQuery(BaseModel):
    query: str
    filters: Optional[dict] = None
    limit: Optional[int] = 10


# Initialize OpenAI components - will be set up in lifespan
embeddings = None
vectorstore = None
retriever = None

# Initialize Redis for conversation history
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD", None),
)

# Prompt templates for token manager integration
rephrase_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question about restaurants, in its original language.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""

restaurant_template = """You are a knowledgeable restaurant expert and culinary advisor. Answer the question based only on the following context about restaurants.

Context:
{context}

Question: {question}

Guidelines:
- Focus on restaurants, cuisine, dining experiences, and food
- Provide detailed, helpful information about restaurants
- If asked about specific restaurants, mention their location, cuisine type, and key features
- For Michelin-starred restaurants, mention their star rating
- If you don't know something from the context, say so
- Be enthusiastic about food and dining experiences
- Suggest similar restaurants when appropriate

Answer:"""

def rephrase_question(chat_history: str, question: str) -> str:
    """Rephrase follow-up question using token manager."""
    return call_openai_chat(
        system_prompt="You are a helpful assistant that rephrases questions about restaurants.",
        user_prompt=f"Chat History:\n{chat_history}\n\nFollow Up Input: {question}\n\nRephrase this as a standalone question about restaurants:",
        force_model="gpt-4o-mini"  # Use mini for simple rephrasing
    )

def generate_response(context: str, question: str) -> str:
    """Generate restaurant response using token manager."""
    return call_openai_chat(
        system_prompt="You are a knowledgeable restaurant expert and culinary advisor.",
        user_prompt=f"Context:\n{context}\n\nQuestion: {question}\n\nPlease answer based only on the context provided. Focus on restaurants, cuisine, and dining experiences. For Michelin-starred restaurants, mention their rating. If you don't know something from the context, say so.",
        force_model=None  # Allow automatic model switching
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global embeddings, vectorstore, retriever
    
    try:
        # Test Redis connection first (doesn't use OpenAI)
        redis_client.ping()
        logger.info("Redis connection established")
        
        # Try to initialize OpenAI components with token manager
        try:
            # Test token manager availability
            test_response = call_openai_chat(
                system_prompt="You are a test assistant.",
                user_prompt="Say 'OK' if you can respond.",
                force_model="gpt-4o-mini"
            )
            
            if test_response:
                logger.info("OpenAI token manager working - initializing embeddings")
                embeddings = OpenAIEmbeddings()
                
                # Initialize vector store
                vectorstore = PGVector(
                    collection_name="restaurant_embeddings",
                    connection=CONNECTION_STRING,
                    embeddings=embeddings,
                    use_jsonb=True,
                )
                
                retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
                logger.info("Vector store connection established")
            else:
                logger.warning("OpenAI token limits reached - running in fallback mode")
                
        except Exception as openai_error:
            logger.warning(f"OpenAI service unavailable: {openai_error} - running in fallback mode")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Don't raise - allow service to start in fallback mode
        yield
    finally:
        # Cleanup if needed
        pass


app = FastAPI(
    title="Restaurant RAG Service",
    description="RAG service for restaurant queries and recommendations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Restaurant RAG Service", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Redis (always required)
        redis_client.ping()
        
        services = ["redis"]
        
        # Test vector store if available
        if vectorstore is not None:
            vectorstore.similarity_search("test", k=1)
            services.append("vectorstore")
            services.append("openai")
        
        return {
            "status": "healthy", 
            "services": services,
            "mode": "full" if vectorstore is not None else "fallback"
        }
    except Exception as e:
        return {
            "status": "healthy",
            "services": ["redis"],
            "mode": "fallback",
            "note": "OpenAI services unavailable, running in fallback mode"
        }


@app.post("/query")
async def query_restaurants(request: RestaurantQuery):
    """Query restaurants using RAG with token manager."""
    try:
        # Check if full RAG is available
        if retriever is None:
            # Fallback mode - provide helpful response
            fallback_response = f"""I understand you're looking for information about "{request.query}". 

Currently, our AI restaurant advisor is running in limited mode. However, I can help you with:

• General restaurant recommendations
• Information about cuisine types
• Dining experience advice
• Restaurant features and amenities

For specific restaurant details, menu information, and personalized recommendations, please try again later when our full AI service is available.

Is there something specific about restaurants or dining I can help you with?"""
            
            return {
                "response": fallback_response,
                "sources": [],
                "mode": "fallback"
            }
        
        # Apply filters if provided
        if request.filters:
            # TODO: Implement metadata filtering
            pass
        
        # Get relevant documents
        docs = retriever.get_relevant_documents(request.query)
        
        # Generate response using token manager
        context = "\n\n".join([doc.page_content for doc in docs])
        response = generate_response(context, request.query)
        
        if not response:
            response = "I apologize, but I'm unable to process your request at the moment due to token limits. Please try again later."
        
        return {
            "response": response,
            "sources": [
                {
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in docs[:3]  # Return top 3 sources
            ],
            "mode": "full"
        }
        
    except Exception as e:
        logger.error(f"Error in query_restaurants: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversation/start")
async def start_conversation():
    """Start a new conversation."""
    try:
        conversation_id = str(uuid.uuid4())
        redis_client.set(
            f"conversation:{conversation_id}", 
            json.dumps([]),
            ex=3600  # Expire after 1 hour
        )
        
        return {"conversation_id": conversation_id}
    
    except Exception as e:
        logger.error(f"Error starting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversation/{conversation_id}")
async def conversation(conversation_id: str, request: ConversationRequest):
    """Continue a conversation using token manager."""
    try:
        # Get conversation history
        conversation_key = f"conversation:{conversation_id}"
        conversation_history_json = redis_client.get(conversation_key)
        
        if conversation_history_json is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        chat_history = json.loads(conversation_history_json.decode("utf-8"))
        
        logger.info(f"Conversation ID: {conversation_id}, Input: {request.message}")
        
        # Check if full RAG is available
        if retriever is None:
            # Fallback mode - provide contextual response
            fallback_responses = [
                "That's an interesting question about restaurants! While our full AI service is temporarily unavailable, I'd be happy to help with general dining advice.",
                "I appreciate your question about dining! Our detailed restaurant database is currently limited, but I can offer some general guidance about restaurants and cuisine.",
                "Thanks for your restaurant question! While I can't access our complete database right now, I'm here to help with general dining recommendations."
            ]
            
            # Simple response selection based on message length
            response_idx = len(request.message) % len(fallback_responses)
            response = fallback_responses[response_idx]
            
            # Add specific context if possible
            if any(word in request.message.lower() for word in ["michelin", "star", "fine dining"]):
                response += " For Michelin-starred restaurants, I'd recommend checking the official Michelin Guide for the most current information."
            elif any(word in request.message.lower() for word in ["location", "near", "close"]):
                response += " For location-specific recommendations, local review sites and maps can be very helpful."
        else:
            # Full RAG mode
            # Format chat history for rephrasing
            chat_history_text = "\n".join([
                f"{'Human' if msg['role'] == 'human' else 'Assistant'}: {msg['content']}"
                for msg in chat_history[-4:]  # Last 4 messages for context
            ])
            
            # Step 1: Rephrase question if there's conversation history
            if chat_history:
                rephrased_question = rephrase_question(chat_history_text, request.message)
                if not rephrased_question:
                    # Fallback to original question if rephrasing fails
                    rephrased_question = request.message
            else:
                rephrased_question = request.message
            
            # Step 2: Get relevant documents
            docs = retriever.get_relevant_documents(rephrased_question)
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Step 3: Generate response using token manager
            response = generate_response(context, rephrased_question)
            
            if not response:
                response = "I apologize, but I'm unable to process your request at the moment due to token limits. Please try again later."
        
        # Update conversation history
        chat_history.append({"role": "human", "content": request.message})
        chat_history.append({"role": "assistant", "content": response})
        
        # Save updated history
        redis_client.set(
            conversation_key,
            json.dumps(chat_history),
            ex=3600  # Extend expiration
        )
        
        return {
            "response": response,
            "conversation_id": conversation_id,
            "history": chat_history[-2:],  # Return last 2 messages
            "mode": "full" if retriever is not None else "fallback"
        }
        
    except Exception as e:
        logger.error(f"Error in conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/conversation/{conversation_id}")
async def end_conversation(conversation_id: str):
    """End a conversation."""
    try:
        conversation_key = f"conversation:{conversation_id}"
        
        if not redis_client.exists(conversation_key):
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        redis_client.delete(conversation_key)
        
        return {"message": "Conversation ended"}
    
    except Exception as e:
        logger.error(f"Error ending conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embeddings/generate")
async def generate_embeddings(content: str, metadata: dict = None):
    """Generate embeddings for content."""
    try:
        # Generate embeddings
        embedding = embeddings.embed_query(content)
        
        # Store in vector database
        vectorstore.add_texts(
            texts=[content],
            metadatas=[metadata or {}]
        )
        
        return {"message": "Embeddings generated and stored"}
    
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/embeddings/search")
async def search_embeddings(query: str, k: int = 5):
    """Search for similar embeddings."""
    try:
        results = vectorstore.similarity_search(query, k=k)
        
        return {
            "results": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": getattr(doc, 'score', None)
                }
                for doc in results
            ]
        }
    
    except Exception as e:
        logger.error(f"Error searching embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/token-usage")
async def get_token_usage():
    """Get current token usage status."""
    try:
        usage_summary = get_token_usage_summary()
        return {
            "current_model": usage_summary["current_model"],
            "date": usage_summary["date"],
            "usage_by_model": usage_summary["usage_by_model"],
            "last_completed_row": usage_summary["last_completed_row"],
            "status": "active" if usage_summary["current_model"] else "exhausted"
        }
    
    except Exception as e:
        logger.error(f"Error getting token usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)