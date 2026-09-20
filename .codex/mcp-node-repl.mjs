#!/usr/bin/env node
// Minimal MCP stdio server: JS eval tool "js" (Linux stand-in for ChatGPT node_repl)
import vm from 'node:vm';
import readline from 'node:readline';

const rl = readline.createInterface({ input: process.stdin, terminal: false });
const send = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');

rl.on('line', (line) => {
  line = line.trim();
  if (!line) return;
  let msg;
  try { msg = JSON.parse(line); } catch { return; }
  const { id, method, params } = msg;
  if (method === 'initialize') {
    send({ jsonrpc: '2.0', id, result: {
      protocolVersion: params?.protocolVersion || '2025-03-26',
      capabilities: { tools: {} },
      serverInfo: { name: 'node-repl-linux', version: '1.0.0' },
    }});
    return;
  }
  if (method === 'tools/list') {
    send({ jsonrpc: '2.0', id, result: { tools: [{
      name: 'js',
      description: 'Evaluate JavaScript code and return the result',
      inputSchema: { type: 'object', properties: { code: { type: 'string' } }, required: ['code'] },
    }]}});
    return;
  }
  if (method === 'tools/call' && params?.name === 'js') {
    const code = String(params.arguments?.code ?? '');
    try {
      const result = vm.runInNewContext(code, { console: { log: (...a) => a.join(' ') } }, { timeout: 10000 });
      send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: String(result) }] } });
    } catch (e) {
      send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: String(e) }] }, error: undefined, isError: true });
    }
    return;
  }
  if (method === 'ping') { send({ jsonrpc: '2.0', id, result: {} }); return; }
  if (id !== undefined && (method?.startsWith('tools/') || method === 'resources/list' || method === 'prompts/list')) {
    send({ jsonrpc: '2.0', id, result: {} });
    return;
  }
  // notifications: no response
});
