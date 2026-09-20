<template>
  <div class="app-shell">
    <!-- Sidebar -->
    <ChatSidebar :loading="isLoading" @quick-question="sendMessage" />

    <!-- Main chat area -->
    <main class="chat-main">
      <!-- Header -->
      <header class="chat-header">
        <div class="header-info">
          <h1 class="header-title">Chat com Notícias</h1>
          <span class="header-badge">RAG · LangChain · Groq</span>
        </div>
        <button class="clear-btn" title="Limpar conversa" @click="clearChat">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14H6L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4h6v2" />
          </svg>
        </button>
      </header>

      <!-- Messages -->
      <section ref="messagesContainer" class="messages-area">
        <!-- Empty state -->
        <div v-if="messages.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <h2 class="empty-title">Como posso ajudar?</h2>
          <p class="empty-sub">
            Faça uma pergunta sobre as notícias ingeridas ou use uma das
            <strong>Perguntas Rápidas</strong> na barra lateral.
          </p>
        </div>

        <!-- Message list -->
        <div class="messages-list">
          <ChatMessage v-for="msg in messages" :key="msg.id" :message="msg" />
        </div>
      </section>

      <!-- Error banner -->
      <transition name="fade">
        <div v-if="errorMessage" class="error-banner">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="error-icon">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {{ errorMessage }}
        </div>
      </transition>

      <!-- Input area -->
      <footer class="input-area">
        <div class="input-wrapper">
          <textarea
            id="chat-input"
            ref="inputRef"
            v-model="inputText"
            class="chat-input"
            placeholder="Faça uma pergunta sobre as notícias..."
            rows="1"
            :disabled="isLoading"
            @keydown.enter.prevent="handleEnter"
            @input="autoResize"
          />
          <button
            id="send-btn"
            class="send-btn"
            :disabled="!inputText.trim() || isLoading"
            @click="sendMessage(inputText)"
          >
            <svg v-if="!isLoading" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
            <span v-else class="spinner" />
          </button>
        </div>
        <p class="input-hint">Enter para enviar · Shift+Enter para nova linha</p>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick } from "vue";
import axios from "axios";
import ChatSidebar from "./components/ChatSidebar.vue";
import ChatMessage from "./components/ChatMessage.vue";

// ─── State ────────────────────────────────────────────────────────────────────

const messages = ref([]);
const inputText = ref("");
const isLoading = ref(false);
const errorMessage = ref("");
const messagesContainer = ref(null);
const inputRef = ref(null);

let msgCounter = 0;
const uid = () => ++msgCounter;

// ─── Actions ──────────────────────────────────────────────────────────────────

async function sendMessage(text) {
  const question = (typeof text === "string" ? text : inputText.value).trim();
  if (!question || isLoading.value) return;

  errorMessage.value = "";
  inputText.value = "";
  resetTextareaHeight();

  // Push user message
  messages.value.push({ id: uid(), role: "user", content: question });

  // Push loading placeholder for assistant
  const loadingMsg = { id: uid(), role: "assistant", content: "", isLoading: true };
  messages.value.push(loadingMsg);
  await scrollToBottom();

  isLoading.value = true;

  try {
    const { data } = await axios.post("/chat", { question });
    // Replace loading placeholder with real answer
    const idx = messages.value.findIndex((m) => m.id === loadingMsg.id);
    if (idx !== -1) {
      messages.value[idx] = {
        id: loadingMsg.id,
        role: "assistant",
        content: data.answer,
        sources: data.sources || [],
        isLoading: false,
      };
    }
  } catch (err) {
    // Remove loading placeholder and show error
    messages.value = messages.value.filter((m) => m.id !== loadingMsg.id);
    errorMessage.value =
      "Erro ao obter resposta: " +
      (err.response?.data?.detail || err.message || "Tente novamente.");
    setTimeout(() => (errorMessage.value = ""), 5000);
  } finally {
    isLoading.value = false;
    await scrollToBottom();
    inputRef.value?.focus();
  }
}

function clearChat() {
  messages.value = [];
  errorMessage.value = "";
}

function handleEnter(event) {
  if (event.shiftKey) return; // allow newline
  sendMessage(inputText.value);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function scrollToBottom() {
  await nextTick();
  const el = messagesContainer.value;
  if (el) el.scrollTop = el.scrollHeight;
}

function autoResize(event) {
  const ta = event.target;
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
}

function resetTextareaHeight() {
  if (inputRef.value) inputRef.value.style.height = "auto";
}
</script>

<style scoped>
/* ── Shell ───────────────────────────────────────────────────────────────── */
.app-shell {
  display: flex;
  height: 100dvh;
  overflow: hidden;
  background: var(--color-bg-primary);
}

/* ── Main ────────────────────────────────────────────────────────────────── */
.chat-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  overflow: hidden;
}

/* ── Header ──────────────────────────────────────────────────────────────── */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  flex-shrink: 0;
}
.header-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.header-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}
.header-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-accent-light);
  background: var(--color-accent-glow);
  padding: 2px 8px;
  border-radius: 99px;
  border: 1px solid rgba(124, 58, 237, 0.3);
}
.clear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}
.clear-btn:hover {
  border-color: #ef4444;
  color: #f87171;
  background: rgba(239, 68, 68, 0.08);
}
.clear-btn svg {
  width: 16px;
  height: 16px;
}

/* ── Messages ─────────────────────────────────────────────────────────────── */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  scroll-behavior: smooth;
}
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
  align-items: center;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  gap: 0.75rem;
  padding: 2rem;
  color: var(--color-text-secondary);
}
.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  color: var(--color-accent-light);
}
.empty-icon svg {
  width: 32px;
  height: 32px;
}
.empty-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-primary);
}
.empty-sub {
  margin: 0;
  font-size: 0.85rem;
  max-width: 360px;
  line-height: 1.6;
}

/* ── Error banner ─────────────────────────────────────────────────────────── */
.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 1.5rem 0.5rem;
  padding: 0.6rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #f87171;
  font-size: 0.82rem;
  flex-shrink: 0;
}
.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Input area ───────────────────────────────────────────────────────────── */
.input-area {
  padding: 1rem 1.5rem 1.25rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  flex-shrink: 0;
}
.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 0.6rem;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 0.5rem 0.5rem 0.5rem 1rem;
  transition: border-color 0.2s;
}
.input-wrapper:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-glow);
}
.chat-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: var(--color-text-primary);
  font-size: 0.9rem;
  font-family: "Inter", sans-serif;
  line-height: 1.5;
  max-height: 140px;
  overflow-y: auto;
}
.chat-input::placeholder {
  color: var(--color-text-muted);
}
.chat-input:disabled {
  opacity: 0.6;
}
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, var(--color-accent), #4f46e5);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s ease;
}
.send-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: scale(1.05);
  box-shadow: 0 4px 12px var(--color-accent-glow);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}
.send-btn svg {
  width: 18px;
  height: 18px;
}
.input-hint {
  margin: 0.4rem 0 0;
  font-size: 0.68rem;
  color: var(--color-text-muted);
  text-align: right;
}

/* Spinner */
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── Responsive ───────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .app-shell {
    flex-direction: column;
  }
}
</style>
