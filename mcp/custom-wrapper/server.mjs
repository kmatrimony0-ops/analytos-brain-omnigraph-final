#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const statePath = process.env.ANALYTOS_GRAPH_STATE || path.join(repoRoot, ".local_graph", "state.json");
const actor = process.env.ANALYTOS_ACTOR || "content-agent";

function state() {
  return JSON.parse(fs.readFileSync(statePath, "utf8"));
}
function canRead(node) {
  const v = node.data?.visibility;
  if (actor === "content-agent") return ["Product", "Feature", "ProofPoint", "Metric", "SourceDocument"].includes(node.type) && v !== "internal_only";
  if (actor === "gtm-agent") return ["Product", "Feature", "ProofPoint", "Metric", "ICPSegment", "Persona", "SourceDocument"].includes(node.type) && v !== "internal_only";
  return true;
}
function nodes() {
  return Object.values(state().branches.main.nodes).filter(canRead);
}
function search(q) {
  const terms = q.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  return nodes().map(n => ({score: terms.filter(t => JSON.stringify(n).toLowerCase().includes(t)).length, ...n})).filter(n => n.score > 0).sort((a,b) => b.score - a.score).slice(0, 10);
}

const server = new McpServer({ name: "analytos-brain", version: "0.1.0" });

server.tool("search_knowledge", { query: z.string() }, async ({ query }) => ({
  content: [{ type: "text", text: JSON.stringify(search(query), null, 2) }]
}));

server.tool("get_product_context", { product: z.string() }, async ({ product }) => ({
  content: [{ type: "text", text: JSON.stringify(search(product), null, 2) }]
}));

server.tool("try_read_email_threads", {}, async () => {
  const all = Object.values(state().branches.main.nodes).filter(n => n.type === "EmailThread");
  const visible = all.filter(canRead);
  return { content: [{ type: "text", text: JSON.stringify({ actor, visible_count: visible.length, denied_count: all.length - visible.length }, null, 2) }] };
});

const transport = new StdioServerTransport();
await server.connect(transport);
