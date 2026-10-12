// An isolated PostgreSQL WASM engine, used only by explicit operations tests.
import { pathToFileURL } from 'node:url';
import { createInterface } from 'node:readline';
const { PGlite } = await import(pathToFileURL(process.env.OPS_PGLITE_MODULE).href);
const db = new PGlite();
await db.waitReady;
process.stdout.write('ready\n');
for await (const line of createInterface({ input: process.stdin })) {
  try {
    const request = JSON.parse(line);
    const result = request.script ? await db.exec(request.sql) : await db.query(request.sql, request.params || []);
    process.stdout.write(JSON.stringify({ result }) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({ error: { code: error.code, message: error.message } }) + '\n');
  }
}
await db.close();
