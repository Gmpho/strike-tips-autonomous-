import { WebWorkerMLCEngineHandler } from "@mlc-ai/web-llm";

// Instantiate the background WebWorkerMLCEngineHandler
const handler = new WebWorkerMLCEngineHandler();

self.onmessage = (msg: MessageEvent) => {
  handler.onmessage(msg);
};
