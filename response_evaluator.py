"""
Response Quality Evaluator
Uses OpenAI to evaluate if Krishna's responses are relevant and helpful
"""

import asyncio
from openai import AsyncOpenAI
from config import Config
import json

class ResponseEvaluator:
    """Evaluates response quality using OpenAI"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Fast and cheap for evaluation
        print("✅ Response Evaluator initialized (OpenAI)")
    
    async def evaluate(self, user_query: str, krishna_response: str, rag_context: str = "") -> dict:
        """
        Evaluate Krishna's response quality
        
        Returns:
            dict with scores and feedback:
            - relevance_score: 1-10 (Does response address user's question?)
            - accuracy_score: 1-10 (Are Gita verses used correctly?)
            - helpfulness_score: 1-10 (Is advice practical and actionable?)
            - language_match: True/False (Does response match user's language?)
            - overall_score: Average of all scores
            - feedback: Text feedback
        """
        
        eval_prompt = f"""You are evaluating a spiritual AI assistant (Lord Krishna from Bhagavad Gita).

USER QUERY: {user_query}

KRISHNA'S RESPONSE: {krishna_response}

RAG CONTEXT PROVIDED (Gita verses retrieved): 
{rag_context if rag_context else "No RAG context was used"}

EVALUATE THE RESPONSE ON THESE CRITERIA (1-10 scale):

1. RELEVANCE (1-10): Does the response directly address the user's question/problem?
2. ACCURACY (1-10): Are any Gita verses quoted correctly and used appropriately?
3. HELPFULNESS (1-10): Is the advice practical and actionable for modern life?
4. LANGUAGE_MATCH: Did Krishna respond in the same language as the user? (true/false)
   - If user spoke Hindi → Krishna should reply in Hindi
   - If user spoke English → Krishna should reply in English
   - If user spoke Hinglish → Krishna should reply in Hinglish

Respond in this exact JSON format:
{{
    "relevance_score": <1-10>,
    "accuracy_score": <1-10>,
    "helpfulness_score": <1-10>,
    "language_match": <true/false>,
    "feedback": "<Brief feedback on what was good and what could be improved>",
    "is_rag_used_well": <true/false>,
    "verse_quality": "<Good/Average/Poor/No verses used>"
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator for spiritual AI assistants. Be fair and constructive."},
                    {"role": "user", "content": eval_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON from response
            # Handle potential markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            result = json.loads(result_text)
            
            # Calculate overall score
            relevance = result.get("relevance_score", 5)
            accuracy = result.get("accuracy_score", 5)
            helpfulness = result.get("helpfulness_score", 5)
            
            result["overall_score"] = round((relevance + accuracy + helpfulness) / 3, 1)
            
            return result
            
        except Exception as e:
            print(f"⚠️ Evaluation error: {e}")
            return {
                "relevance_score": -1,
                "accuracy_score": -1,
                "helpfulness_score": -1,
                "language_match": None,
                "overall_score": -1,
                "feedback": f"Evaluation failed: {str(e)}",
                "is_rag_used_well": None,
                "verse_quality": "Unknown"
            }
    
    def print_evaluation(self, eval_result: dict) -> None:
        """Print evaluation results in a formatted way"""
        print("\n" + "="*60)
        print("📊 RESPONSE QUALITY EVALUATION")
        print("="*60)
        
        overall = eval_result.get("overall_score", -1)
        
        # Color based on score
        if overall >= 8:
            grade = "🌟 EXCELLENT"
            color = "\033[92m"  # Green
        elif overall >= 6:
            grade = "✅ GOOD"
            color = "\033[93m"  # Yellow
        elif overall >= 4:
            grade = "⚠️ NEEDS IMPROVEMENT"
            color = "\033[93m"
        else:
            grade = "❌ POOR"
            color = "\033[91m"  # Red
        
        reset = "\033[0m"
        
        print(f"\n{color}Overall Score: {overall}/10 - {grade}{reset}\n")
        
        print(f"  📌 Relevance:    {eval_result.get('relevance_score', '?')}/10")
        print(f"  📖 Accuracy:     {eval_result.get('accuracy_score', '?')}/10")
        print(f"  💡 Helpfulness:  {eval_result.get('helpfulness_score', '?')}/10")
        
        lang_match = eval_result.get('language_match')
        lang_icon = "✅" if lang_match else "❌"
        print(f"  🌐 Language:     {lang_icon} {'Matched' if lang_match else 'Mismatched'}")
        
        rag_used = eval_result.get('is_rag_used_well')
        rag_icon = "✅" if rag_used else "⚠️"
        print(f"  📚 RAG Used:     {rag_icon} {eval_result.get('verse_quality', 'Unknown')}")
        
        print(f"\n  💬 Feedback: {eval_result.get('feedback', 'No feedback')}")
        print("="*60 + "\n")


# Singleton instance
_evaluator_instance = None

def get_evaluator() -> ResponseEvaluator:
    """Get or create singleton evaluator instance"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = ResponseEvaluator()
    return _evaluator_instance


# Test function
async def test_evaluation():
    """Test the evaluator with sample data"""
    evaluator = get_evaluator()
    
    # Test case 1: English query
    result = await evaluator.evaluate(
        user_query="How to deal with anger?",
        krishna_response="""My friend, anger is a powerful enemy. As I said in the Gita, 
"Krodhat bhavati sammohah" - from anger comes delusion. 
Here's what you can do:
1. When anger rises, take 3 deep breaths
2. Remember - the person who angered you is also struggling
3. Practice daily meditation for just 5 minutes
The fire of anger burns you first before reaching others. Stay calm, Partha.""",
        rag_context="Chapter 2, Verse 63: From anger arises delusion..."
    )
    
    evaluator.print_evaluation(result)
    
    # Test case 2: Hindi query
    result2 = await evaluator.evaluate(
        user_query="मुझे बहुत stress हो रहा है",
        krishna_response="""Dear seeker, I understand you are feeling stressed. 
Remember what I said: Karmanye vadhikaraste ma phaleshu kadachana.
Focus on your actions, not the results.""",
        rag_context="Chapter 2, Verse 47..."
    )
    
    evaluator.print_evaluation(result2)


if __name__ == "__main__":
    asyncio.run(test_evaluation())
