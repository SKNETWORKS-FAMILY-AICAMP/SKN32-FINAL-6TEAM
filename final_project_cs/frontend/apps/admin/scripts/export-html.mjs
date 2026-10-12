import { build } from 'esbuild';
import { writeFile } from 'node:fs/promises';
const result = await build({ entryPoints: ['src/standalone.tsx'], bundle: true, minify: true, write: false, outfile: 'admin.js', define: { 'process.env.NODE_ENV': '"production"' }, target: ['es2022'], legalComments: 'inline', charset: 'utf8' });
const script = result.outputFiles.find(file => file.path.endsWith('.js')).text.replace(/<\/script/gi, '<\\/script');
const css = result.outputFiles.find(file => file.path.endsWith('.css')).text.replace(/<\/style/gi, '<\\/style');
const html = `<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="triPilot 운영자 콘솔 — 인터넷 없이 실행하는 단일 HTML 시나리오"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>triPilot · 운영 시나리오</title><style>${css}</style></head><body><div id="root"></div><noscript>이 시나리오는 브라우저의 JavaScript를 켜야 동작합니다. 데모 데이터는 서버에 저장되지 않습니다.</noscript><script>${script}</script></body></html>\n`;
await writeFile('mockups/admin-scenario.html', html, 'utf8');
console.log(`단일 HTML 생성: mockups/admin-scenario.html (${(Buffer.byteLength(html)/1024).toFixed(1)} KB) · 네트워크 불필요`);
