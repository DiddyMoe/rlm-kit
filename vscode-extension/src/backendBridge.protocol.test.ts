import * as assert from "assert";

import { BackendBridge } from "./backendBridge";

type PendingCompletionMap = Map<
  string,
  {
    resolve: (value: string) => void;
    reject: (error: Error) => void;
  }
>;

type PendingExecMap = Map<
  string,
  {
    resolve: (value: { stdout: string; stderr: string; error?: string | boolean }) => void;
    reject: (error: Error) => void;
  }
>;

type BackendBridgeInternals = {
  onStdout: (chunk: string) => void;
  handleMessage: (message: { type: string; [key: string]: unknown }) => void;
  ready: boolean;
  readyResolve: (() => void) | null;
  pendingCompletions: PendingCompletionMap;
  pendingExecs: PendingExecMap;
};

function asInternals(bridge: BackendBridge): BackendBridgeInternals {
  return bridge as unknown as BackendBridgeInternals;
}

function testReadyMessageResolvesBridge(): void {
  const bridge = new BackendBridge("python");
  const internal = asInternals(bridge);
  let resolved = false;

  internal.readyResolve = () => {
    resolved = true;
  };

  internal.handleMessage({ type: "ready" });

  assert.strictEqual(internal.ready, true);
  assert.strictEqual(resolved, true);
}

function testFragmentedStdoutChunkParsesJsonLine(): void {
  const bridge = new BackendBridge("python");
  const internal = asInternals(bridge);
  let received = "";

  bridge.setChunkHandler((nonce: string, text: string) => {
    assert.strictEqual(nonce, "n1");
    received = text;
  });

  internal.onStdout('{"type":"chunk","nonce":"n1","text":"he');
  internal.onStdout('llo"}\n');

  assert.strictEqual(received, "hello");
}

function testResultMessageResolvesPendingCompletion(): void {
  const bridge = new BackendBridge("python");
  const internal = asInternals(bridge);
  let resolvedText = "";

  internal.pendingCompletions.set("nonce-result", {
    resolve: (value: string) => {
      resolvedText = value;
    },
    reject: () => {
      throw new Error("Unexpected rejection");
    },
  });

  internal.handleMessage({
    type: "result",
    nonce: "nonce-result",
    text: "final output",
  });

  assert.strictEqual(resolvedText, "final output");
  assert.strictEqual(internal.pendingCompletions.has("nonce-result"), false);
}

function testErrorMessageRejectsPendingExec(): void {
  const bridge = new BackendBridge("python");
  const internal = asInternals(bridge);
  let rejectedMessage = "";

  internal.pendingExecs.set("nonce-exec", {
    resolve: () => {
      throw new Error("Unexpected resolve");
    },
    reject: (error: Error) => {
      rejectedMessage = error.message;
    },
  });

  internal.handleMessage({
    type: "error",
    nonce: "nonce-exec",
    error: "exec failed",
  });

  assert.strictEqual(rejectedMessage, "exec failed");
  assert.strictEqual(internal.pendingExecs.has("nonce-exec"), false);
}

function runAllTests(): void {
  testReadyMessageResolvesBridge();
  testFragmentedStdoutChunkParsesJsonLine();
  testResultMessageResolvesPendingCompletion();
  testErrorMessageRejectsPendingExec();
  console.log("backendBridge.protocol.test.ts: all tests passed");
}

runAllTests();
