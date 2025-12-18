// BAML Client Configurations for Scraper Agent Architecture

// ============================================================================
// AWS Bedrock Client (Primary for Production)
// ============================================================================

client<llm> ClaudeBedrock {
  provider aws-bedrock
  retry_policy DefaultRetry
  options {
    model "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    region "us-east-1"
    // max_tokens: Not supported in BAML 0.214.0 client options
    // Token limits must be configured in the runtime invocation
    // AWS credentials are read from environment variables:
    // AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional)
  }
}

// ============================================================================
// Anthropic API Client (Alternative/Development)
// ============================================================================

client<llm> ClaudeAnthropic {
  provider anthropic
  retry_policy DefaultRetry
  options {
    model "claude-sonnet-4-5-20251101"
    // max_tokens: Not supported in BAML 0.214.0 client options
    // Token limits must be configured in the runtime invocation
    // API key is read from ANTHROPIC_API_KEY environment variable
  }
}

// ============================================================================
// Retry Policy for All Clients
// ============================================================================

retry_policy DefaultRetry {
  max_retries 3
  strategy {
    type exponential_backoff
  }
}
