"""
Conversational interface using Anthropic SDK with RAG
"""
import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

from src.retrieval.retriever import SemanticRetriever, RetrievalResult
from config.settings import settings

logger = logging.getLogger(__name__)


class VocBenchAssistant:
    """Conversational AI assistant for VocBench knowledge"""

    def __init__(
        self,
        retriever: SemanticRetriever,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 2048,
        temperature: float = 0.7
    ):
        """
        Initialize assistant

        Args:
            retriever: SemanticRetriever instance
            api_key: Anthropic API key (from settings if None)
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
        """
        self.retriever = retriever
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize Anthropic client
        api_key = api_key or settings.anthropic_api_key
        self.client = Anthropic(api_key=api_key)

        logger.info(f"VocBenchAssistant initialized with model {model}")

    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        include_sources: bool = True,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Chat with the assistant

        Args:
            user_message: User's message
            conversation_history: Previous conversation messages
            top_k: Number of relevant documents to retrieve
            include_sources: Include source references in response
            system_prompt: Custom system prompt

        Returns:
            Dictionary with response and metadata
        """
        if not user_message or not user_message.strip():
            return {
                'response': "I didn't receive a message. How can I help you with VocBench?",
                'sources': [],
                'error': 'Empty message'
            }

        logger.info(f"Processing query: {user_message[:100]}...")

        # Retrieve relevant context
        retrieved_docs = self.retriever.retrieve(user_message, top_k=top_k)
        retrieval_result = RetrievalResult(retrieved_docs, user_message)

        # Build context from retrieved documents
        context = retrieval_result.format_for_llm(max_chunks=top_k)

        # Build system prompt
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        # Build messages
        messages = []

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message with context
        user_message_with_context = f"""Context from VocBench knowledge base:
{context}

User question: {user_message}

Please answer based on the context provided above. If the context doesn't contain relevant information, say so clearly."""

        messages.append({
            "role": "user",
            "content": user_message_with_context
        })

        try:
            # Call Anthropic API
            logger.debug(f"Calling Anthropic API with model {self.model}")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=messages
            )

            # Extract response text
            assistant_message = response.content[0].text

            # Build response
            result = {
                'response': assistant_message,
                'sources': retrieved_docs if include_sources else [],
                'model': self.model,
                'usage': {
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens
                }
            }

            logger.info(f"Generated response with {len(retrieved_docs)} sources")
            return result

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return {
                'response': "I encountered an error processing your request. Please try again.",
                'sources': [],
                'error': str(e)
            }

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt"""
        return """You are a helpful AI assistant specialized in VocBench, a collaborative platform for developing SKOS/SKOS-XL thesauri, ontologies, and generic RDF datasets.

Your role is to:
1. Answer questions about VocBench features, configuration, and usage
2. Help troubleshoot issues users encounter
3. Provide guidance on best practices for vocabulary management
4. Explain SKOS, RDF, SPARQL, and semantic web concepts in the context of VocBench

Guidelines:
- Base your answers on the provided context from the VocBench user group discussions
- Be concise and practical in your responses
- If the context doesn't contain relevant information, clearly state that and provide general guidance if possible
- Include specific steps or examples when helpful
- Reference the source discussions when relevant
- If you're unsure, acknowledge the uncertainty

Remember: You're helping users work effectively with VocBench for semantic data management."""

    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        system_prompt: Optional[str] = None
    ):
        """
        Stream chat response

        Args:
            user_message: User's message
            conversation_history: Previous conversation messages
            top_k: Number of relevant documents to retrieve
            system_prompt: Custom system prompt

        Yields:
            Response chunks as they're generated
        """
        if not user_message or not user_message.strip():
            yield "I didn't receive a message. How can I help you with VocBench?"
            return

        logger.info(f"Streaming response for query: {user_message[:100]}...")

        # Retrieve relevant context
        retrieved_docs = self.retriever.retrieve(user_message, top_k=top_k)
        retrieval_result = RetrievalResult(retrieved_docs, user_message)
        context = retrieval_result.format_for_llm(max_chunks=top_k)

        # Build system prompt
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        # Build messages
        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        user_message_with_context = f"""Context from VocBench knowledge base:
{context}

User question: {user_message}

Please answer based on the context provided above. If the context doesn't contain relevant information, say so clearly."""

        messages.append({
            "role": "user",
            "content": user_message_with_context
        })

        try:
            # Stream response
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"Error streaming from Anthropic API: {e}")
            yield f"Error: {str(e)}"


class ConversationManager:
    """Manages conversation state and history"""

    def __init__(self, assistant: VocBenchAssistant, max_history: int = 10):
        """
        Initialize conversation manager

        Args:
            assistant: VocBenchAssistant instance
            max_history: Maximum number of message pairs to keep in history
        """
        self.assistant = assistant
        self.max_history = max_history
        self.conversations = {}  # conversation_id -> messages

        logger.info("ConversationManager initialized")

    def start_conversation(self, conversation_id: str):
        """Start a new conversation"""
        self.conversations[conversation_id] = []
        logger.info(f"Started conversation {conversation_id}")

    def send_message(
        self,
        conversation_id: str,
        user_message: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Send a message in a conversation

        Args:
            conversation_id: Conversation ID
            user_message: User's message
            top_k: Number of documents to retrieve

        Returns:
            Assistant's response with metadata
        """
        # Create conversation if it doesn't exist
        if conversation_id not in self.conversations:
            self.start_conversation(conversation_id)

        # Get conversation history
        history = self.conversations[conversation_id]

        # Get response from assistant
        result = self.assistant.chat(
            user_message=user_message,
            conversation_history=history,
            top_k=top_k
        )

        # Update history
        history.append({
            "role": "user",
            "content": user_message
        })
        history.append({
            "role": "assistant",
            "content": result['response']
        })

        # Trim history if needed
        if len(history) > self.max_history * 2:
            self.conversations[conversation_id] = history[-(self.max_history * 2):]

        return result

    def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversations.get(conversation_id, [])

    def clear_conversation(self, conversation_id: str):
        """Clear a conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"Cleared conversation {conversation_id}")

    def list_conversations(self) -> List[str]:
        """List all active conversations"""
        return list(self.conversations.keys())
