from google.genai import types
from typing import List, Dict


class ResearcherAgent:
    def __init__(self, client):
        self.client = client
        self.model = "gemini-2.5-flash"

    def needs_web_search(self, topic: str, context: str, global_token_usage: list) -> bool:
        """
        Quick call to classify if topic/context needs web research.
        Returns True if the topic likely involves events/developments after the LLM knowledge cutoff.
        """
        try:
            context_line = f"\nContext: {context[:500]}" if context else ""

            prompt = (
                f"Does this topic/context require information from after May 2025 to create accurate exam questions?\n"
                f"Topic: {topic}{context_line}\n\n"
                f"Reply with ONLY the word YES or NO.\n"
                f"YES if it involves recent events, policies, budgets, summits, appointments, or any development after May 2025.\n"
                f"NO if it is historical, theoretical, or foundational."
            )

            print(f"[ResearcherAgent] Classifying topic: '{topic[:100]}' (context: {len(context)} chars)")

            resp = self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=5,
                ),
            )

            if hasattr(resp, 'usage_metadata'):
                global_token_usage.append(resp.usage_metadata)

            raw_text = resp.text.strip().upper() if resp.text else ""
            result = raw_text.startswith("YES")
            print(f"[ResearcherAgent] needs_search = {result}")
            return result
        except Exception as e:
            print(f"ResearcherAgent: Classification failed, skipping web search: {e}")
            return False

    def research_topic(self, topic: str, context_hint: str, global_token_usage: list) -> Dict:
        """
        Searches the web via google_search grounding for UPSC-relevant current affairs.
        Returns {'context': str, 'sources': [{'title': str, 'url': str}]}
        """
        try:
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            hint_line = f"\nAdditional context: {context_hint}" if context_hint else ""

            prompt = (
                f"Research this topic for Indian civil services exam (UPSC) question creation.\n"
                f"Topic: {topic}{hint_line}\n\n"
                f"Return ONLY:\n"
                f"- Key facts, data points, dates, and numbers\n"
                f"- Recent developments (last 12 months)\n"
                f"- Government schemes, acts, policies, or verdicts\n"
                f"- International agreements or summits if relevant\n\n"
                f"Format: Bullet points only. No prose. No headers. No explanations.\n"
                f"Focus on UPSC-testable, factual information."
            )

            print(f"[ResearcherAgent] Researching topic: '{topic[:100]}'")

            resp = self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4000,
                    tools=[grounding_tool],
                ),
            )

            if hasattr(resp, 'usage_metadata'):
                global_token_usage.append(resp.usage_metadata)

            context_text = resp.text if resp.text else ""
            sources = self._extract_sources(resp)

            print(f"[ResearcherAgent] Research complete: {len(context_text)} chars, {len(sources)} sources")

            return {
                'context': context_text,
                'sources': sources
            }
        except Exception as e:
            print(f"ResearcherAgent: Web search failed: {e}")
            return {'context': '', 'sources': []}

    def _extract_sources(self, response) -> List[Dict[str, str]]:
        """Extracts source URLs from grounding_metadata."""
        sources = []
        try:
            if (response.candidates
                    and response.candidates[0].grounding_metadata
                    and response.candidates[0].grounding_metadata.grounding_chunks):

                seen_urls = set()
                for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web:
                        url = chunk.web.uri if hasattr(chunk.web, 'uri') else ''
                        title = chunk.web.title if hasattr(chunk.web, 'title') else url
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            sources.append({'title': title, 'url': url})
        except Exception as e:
            print(f"ResearcherAgent: Error extracting sources: {e}")
        return sources
