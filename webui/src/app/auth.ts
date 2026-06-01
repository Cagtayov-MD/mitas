const ACCESS_USERNAME = 'mitas';
const PW_ID_SUFFIX = '_61';

export interface MitasAccessSession {
  authenticated: boolean;
  username?: string | null;
}

export function isValidMitasAccess(username: string, pwId: string): boolean {
  const normalizedUsername = username.trim().toLowerCase();
  const normalizedPwId = pwId.trim();

  return (
    normalizedUsername === ACCESS_USERNAME &&
    normalizedPwId.length > PW_ID_SUFFIX.length &&
    normalizedPwId.endsWith(PW_ID_SUFFIX)
  );
}

export async function fetchMitasAccessSession(): Promise<MitasAccessSession> {
  const response = await fetch('/api/auth/session');
  if (!response.ok) {
    return { authenticated: false };
  }
  return response.json();
}

export async function loginMitasAccess(username: string, pwId: string): Promise<MitasAccessSession> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, pwId }),
  });
  if (!response.ok) {
    throw new Error(await readAccessError(response));
  }
  return response.json();
}

export async function logoutMitasAccess(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
}

async function readAccessError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload.detail || payload.error || response.statusText;
  } catch {
    return response.statusText;
  }
}
