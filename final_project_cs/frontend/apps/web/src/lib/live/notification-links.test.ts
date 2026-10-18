import { describe, expect, it } from 'vitest';
import { localPath } from './auth';

describe('notification login return paths', () => {
  it('keeps the target trip and notices after login', () => {
    const path = '/trips/11111111-2222-4333-8444-555555555555?notices=1';
    expect(localPath(path)).toBe(path);
  });
  it.each(['//other.example/path', '/\\other.example', '/\n/other.example', '/\r/other.example', '/\t/other.example', 'https://other.example', 'javascript:alert(1)', '/a\u0000b'])('refuses an external or control-character return: %j', (path) => {
    expect(localPath(path)).toBe('/');
  });
});
