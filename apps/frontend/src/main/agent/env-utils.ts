/**
 * Utility functions for managing environment variables in agent spawning
 */

import { homedir } from 'os';
import { join } from 'path';
import { existsSync, readFileSync } from 'fs';

/**
 * Read AWS credentials from ~/.aws/credentials file for a specific profile.
 */
function getAWSCredentialsFromProfile(profileName: string): Record<string, string> {
  const credentialsPath = join(homedir(), '.aws', 'credentials');

  if (!existsSync(credentialsPath)) {
    return {};
  }

  try {
    const content = readFileSync(credentialsPath, 'utf-8');
    const lines = content.split('\n');

    let inProfile = false;
    const credentials: Record<string, string> = {};

    for (const line of lines) {
      const trimmed = line.trim();

      // Check for profile header
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        const currentProfile = trimmed.slice(1, -1);
        inProfile = currentProfile === profileName;
        continue;
      }

      // Parse key=value if in the right profile
      if (inProfile && trimmed.includes('=')) {
        const [key, ...valueParts] = trimmed.split('=');
        const value = valueParts.join('=').trim();

        if (key.trim() === 'aws_access_key_id' && value) {
          credentials['AWS_ACCESS_KEY_ID'] = value;
        } else if (key.trim() === 'aws_secret_access_key' && value) {
          credentials['AWS_SECRET_ACCESS_KEY'] = value;
        } else if (key.trim() === 'aws_session_token' && value) {
          credentials['AWS_SESSION_TOKEN'] = value;
        }
      }
    }

    return credentials;
  } catch {
    return {};
  }
}

/**
 * Get fresh AWS credentials for Bedrock mode.
 *
 * When CLAUDE_CODE_USE_BEDROCK is enabled and AWS_PROFILE is set, this reads
 * fresh credentials from ~/.aws/credentials to avoid using stale environment vars.
 */
export function getFreshAWSCredentials(
  combinedEnv?: Record<string, string>
): Record<string, string> {
  const bedrockValue = combinedEnv?.CLAUDE_CODE_USE_BEDROCK ||
                       process.env.CLAUDE_CODE_USE_BEDROCK || '';
  const bedrockEnabled = bedrockValue === '1' || bedrockValue.toLowerCase() === 'true';

  if (!bedrockEnabled) {
    return {};
  }

  const awsProfile = combinedEnv?.AWS_PROFILE || process.env.AWS_PROFILE;
  if (!awsProfile) {
    return {};
  }

  // Read fresh credentials from file
  const freshCreds = getAWSCredentialsFromProfile(awsProfile);

  if (Object.keys(freshCreds).length > 0) {
    console.log(`[env-utils] Read fresh AWS credentials for Bedrock (profile: ${awsProfile})`);
  }

  return freshCreds;
}

/**
 * Get environment variables to clear ANTHROPIC_* vars when in OAuth mode
 *
 * When switching from API Profile mode to OAuth mode, residual ANTHROPIC_*
 * environment variables from process.env can cause authentication failures.
 * This function returns an object with empty strings for these vars when
 * no API profile is active, ensuring OAuth tokens are used correctly.
 *
 * **Why empty strings?** Setting environment variables to empty strings (rather than
 * undefined) ensures they override any stale values from process.env. Python's SDK
 * treats empty strings as falsy in conditional checks like `if token:`, so empty
 * strings effectively disable these authentication parameters without leaving
 * undefined values that might be ignored during object spreading.
 *
 * @param apiProfileEnv - Environment variables from getAPIProfileEnv()
 * @returns Object with empty ANTHROPIC_* vars if in OAuth mode, empty object otherwise
 */
export function getOAuthModeClearVars(
  apiProfileEnv: Record<string, string>,
  combinedEnv?: Record<string, string>
): Record<string, string> {
  // If API profile is active (has ANTHROPIC_* vars), don't clear anything
  if (apiProfileEnv && Object.keys(apiProfileEnv).some(key => key.startsWith('ANTHROPIC_'))) {
    return {};
  }

  // If Bedrock mode is enabled, don't clear ANTHROPIC_* vars - Bedrock handles auth differently
  const bedrockValue = combinedEnv?.CLAUDE_CODE_USE_BEDROCK ||
                       process.env.CLAUDE_CODE_USE_BEDROCK || '';
  const bedrockEnabled = bedrockValue === '1' || bedrockValue.toLowerCase() === 'true';
  if (bedrockEnabled) {
    return {};
  }

  // In OAuth mode (no API profile, no Bedrock), clear all ANTHROPIC_* vars
  // Setting to empty string ensures they override any values from process.env
  // Python's `if token:` checks treat empty strings as falsy
  //
  // IMPORTANT: ANTHROPIC_API_KEY is included to prevent Claude Code from using
  // API keys that may be present in the shell environment instead of OAuth tokens.
  // Without clearing this, Claude Code would show "Claude API" instead of "Claude Max".
  return {
    ANTHROPIC_API_KEY: '',
    ANTHROPIC_AUTH_TOKEN: '',
    ANTHROPIC_BASE_URL: '',
    ANTHROPIC_MODEL: '',
    ANTHROPIC_DEFAULT_HAIKU_MODEL: '',
    ANTHROPIC_DEFAULT_SONNET_MODEL: '',
    ANTHROPIC_DEFAULT_OPUS_MODEL: ''
  };
}
