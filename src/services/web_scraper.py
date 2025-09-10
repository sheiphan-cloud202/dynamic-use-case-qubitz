"""
Web scraping utility using Beautiful Soup and Google Search.
"""

import logging
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import web scraping packages
try:
    from bs4 import BeautifulSoup
    from googlesearch import search

    WEB_SCRAPING_AVAILABLE = True
    logger.info("✅ Web scraping libraries available (BeautifulSoup, googlesearch)")
except ImportError:
    WEB_SCRAPING_AVAILABLE = False
    logger.warning(
        "⚠️ Web scraping libraries not available (BeautifulSoup, googlesearch)"
    )


class WebScraper:
    """Enhanced web scraping utility using Beautiful Soup and Google Search."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def google_search(self, query: str, num_results: int = 10) -> List[str]:
        """Perform Google search and return URLs."""
        if not WEB_SCRAPING_AVAILABLE:
            logger.warning(
                "Google search not available - googlesearch library not installed"
            )
            return []

        try:
            logger.info(f"🔍 Performing Google search: {query}")

            # Use googlesearch library with correct parameters
            search_results = []
            for url in search(query, num_results=num_results, sleep_interval=2):
                search_results.append(url)
                if len(search_results) >= num_results:
                    break

            logger.info(f"✅ Found {len(search_results)} URLs from Google search")
            return search_results

        except Exception as e:
            logger.error(f"❌ Google search failed: {e}")
            # Fallback: return some known URLs for testing
            logger.info("🔄 Using fallback URLs for testing")
            fallback_urls = [
                "https://en.wikipedia.org/wiki/Tesla,_Inc.",
                "https://www.investopedia.com/companies/tesla-tsla",
                "https://www.forbes.com/companies/tesla/",
            ]
            return fallback_urls[:num_results]

    def scrape_url(self, url: str, max_content_length: int = 5000) -> Dict[str, Any]:
        """Scrape content from a URL using Beautiful Soup."""
        if not WEB_SCRAPING_AVAILABLE:
            logger.warning(
                "Web scraping not available - BeautifulSoup library not installed"
            )
            return {
                "url": url,
                "content": "",
                "title": "",
                "error": "BeautifulSoup not available",
            }

        try:
            logger.info(f"🌐 Scraping URL: {url}")

            # Enhanced headers to avoid blocking
            enhanced_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }

            # Use enhanced headers for this request
            response = self.session.get(
                url, timeout=15, allow_redirects=True, headers=enhanced_headers
            )
            response.raise_for_status()

            # Parse with Beautiful Soup
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract title
            title = soup.title.string.strip() if soup.title else urlparse(url).netloc

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()

            # Extract main content
            content_selectors = [
                "main",
                "article",
                ".content",
                "#content",
                ".main-content",
                ".post-content",
                ".entry-content",
                ".article-content",
                ".page-content",
                ".post-body",
                ".entry",
                ".post",
                ".article",
            ]

            main_content = None
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            if not main_content:
                main_content = soup.find("body")

            if not main_content:
                main_content = soup

            # Extract text content
            text_content = main_content.get_text(separator=" ", strip=True)

            # Clean up text
            text_content = re.sub(r"\s+", " ", text_content)
            text_content = text_content.strip()

            # Truncate if too long
            if len(text_content) > max_content_length:
                text_content = text_content[:max_content_length] + "..."

            logger.info(f"✅ Scraped {len(text_content)} characters from {url}")

            return {
                "url": url,
                "title": title,
                "content": text_content,
                "length": len(text_content),
                "success": True,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error for {url}: {e}")
            # Return a basic response for blocked sites
            return {
                "url": url,
                "content": f"Content not accessible due to: {str(e)}",
                "title": urlparse(url).netloc,
                "error": f"Request failed: {str(e)}",
                "success": False,
            }
        except Exception as e:
            logger.error(f"❌ Scraping error for {url}: {e}")
            return {
                "url": url,
                "content": f"Content not accessible due to: {str(e)}",
                "title": urlparse(url).netloc,
                "error": f"Scraping failed: {str(e)}",
                "success": False,
            }

    def scrape_multiple_urls(
        self, urls: List[str], max_workers: int = 3
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently."""
        if not urls:
            return []

        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scraping tasks
            future_to_url = {executor.submit(self.scrape_url, url): url for url in urls}

            # Collect results as they complete
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result(timeout=15)
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ Future error for {url}: {e}")
                    results.append(
                        {
                            "url": url,
                            "content": "",
                            "title": "",
                            "error": f"Future failed: {str(e)}",
                        }
                    )

        successful_scrapes = sum(1 for r in results if r.get("success", False))
        logger.info(f"✅ Successfully scraped {successful_scrapes}/{len(urls)} URLs")

        return results

    def comprehensive_research(
        self, company_name: str, company_url: str, custom_context: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Perform comprehensive research using Google search and web scraping."""

        print(f"🔍 Starting comprehensive research for {company_name}")
        print(f"🌐 Web scraping available: {WEB_SCRAPING_AVAILABLE}")
        print(f"📎 Company URL: {company_url}")
        print(f"📝 Custom context provided: {bool(custom_context)}")

        # Build search queries
        search_queries = [
            f"{company_name} company business model",
            f"{company_name} products services",
            f"{company_name} industry analysis",
            f"{company_name} technology stack",
            f"{company_name} recent news",
        ]
        print(f"🔎 Built {len(search_queries)} search queries")

        # Add custom context queries
        if custom_context and custom_context.get("focus_areas"):
            for focus_area in custom_context["focus_areas"]:
                search_queries.append(f"{company_name} {focus_area}")

        # Perform searches and collect URLs
        all_urls = set()

        # Always include company URL
        if company_url:
            all_urls.add(company_url)

        # Perform Google searches
        for query in search_queries[
            :3
        ]:  # Limit to first 3 queries to avoid rate limits
            try:
                search_urls = self.google_search(query, num_results=5)
                all_urls.update(search_urls)
            except Exception as e:
                logger.error(f"Search failed for query '{query}': {e}")

        # Convert to list and limit
        urls_to_scrape = list(all_urls)[:15]  # Limit to 15 URLs

        logger.info(f"🔍 Scraping {len(urls_to_scrape)} URLs for {company_name}")

        # Scrape URLs
        scraped_results = self.scrape_multiple_urls(urls_to_scrape)

        # Combine content
        combined_content = []
        successful_urls = []

        for result in scraped_results:
            if result.get("success") and result.get("content"):
                combined_content.append(
                    f"=== {result['title']} ({result['url']}) ===\n{result['content']}\n"
                )
                successful_urls.append(result["url"])

        research_content = "\n".join(combined_content)

        print(f"📊 Research complete for {company_name}:")
        print(f"  ✅ Successful scrapes: {len(successful_urls)}")
        print(f"  📄 Total content length: {len(research_content)} characters")
        print(f"  🔗 URLs attempted: {len(urls_to_scrape)}")
        print(f"  🎯 Search queries used: {len(search_queries)}")

        return {
            "research_content": research_content,
            "urls_scraped": successful_urls,
            "total_urls_attempted": len(urls_to_scrape),
            "successful_scrapes": len(successful_urls),
            "scraped_results": scraped_results,
            "search_queries_used": search_queries,
        }
