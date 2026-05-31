#Mock Test Script (Simulating a 500 Server Error)This test uses Python’s native unittest.mock package to intercept the TavilyClient.search method, forcing it to throw an exception that mimics an upstream HTTP 500 error. It then validates that the agent handles the failure gracefully using our orchestration layer instead of crashing
# tests/test_search_failure.py
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure the parent workspace is within Python's search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.web_search import execute_web_search_with_retry

class TestSearchErrorHandling(unittest.TestCase):

    @patch('tavily.TavilyClient')
    def test_web_search_500_internal_server_error(self, mock_tavily_class):
        """Validates that a 500 exception maps safely to a fallback context payload."""
        # 1. Setup the mock instance to mimic a 500 Internal Server error
        mock_instance = MagicMock()
        mock_instance.search.side_effect = Exception("HTTP Error 500: Internal Server Error")
        mock_tavily_class.return_value = mock_instance

        # Temporarily populate a dummy key to bypass initialization checks
        with patch.dict(os.environ, {"TAVILY_API_KEY": "mock_secret_key"}):

            # 2. Fire the execution string (configured for up to 2 retry attempts)
            result = execute_web_search_with_retry(query="Quantum Computing 2026", max_retries=2)

            # 3. Assertions
            # Ensure the client actually attempted the retries before giving up
            self.assertEqual(mock_instance.search.call_count, 3)

            # Verify the tool returned a controlled error payload into the LLM context loop
            self.assertIn("Error: Web search failed due to a network or upstream server error", result)
            self.assertIn("HTTP Error 500: Internal Server Error", result)

if __name__ == '__main__':
    unittest.main()
