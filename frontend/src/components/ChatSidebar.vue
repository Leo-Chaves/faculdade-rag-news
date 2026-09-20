<template>
  <!-- Sidebar -->
  <aside class="sidebar">
    <!-- Logo / Brand -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v2" />
          <path d="M2 20h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H2" />
          <path d="M6 10h8M6 14h8M6 18h4" />
        </svg>
      </div>
      <div class="brand-text">
        <span class="brand-title">RAG News</span>
        <span class="brand-sub">Powered by Groq</span>
      </div>
    </div>

    <!-- Quick Questions -->
    <div class="sidebar-section">
      <p class="sidebar-section-title">Perguntas Rápidas</p>
      <div class="quick-questions">
        <button
          v-for="q in quickQuestions"
          :key="q.id"
          class="quick-btn"
          :disabled="props.loading"
          @click="$emit('quick-question', q.text)"
        >
          <span class="quick-btn-text">{{ q.text }}</span>
        </button>
      </div>
    </div>

    <!-- Ingest BBC Feeds -->
    <div class="sidebar-section">
      <p class="sidebar-section-title">Feeds BBC</p>

      <div class="feeds-list">
        <div v-for="feed in bbcFeeds" :key="feed.label" class="feed-item">
          <span class="feed-dot" />
          <span>{{ feed.label }}</span>
        </div>
      </div>

      <button
        class="ingest-btn"
        :disabled="props.loading || isIngesting"
        @click="handleIngest"
      >
        <span v-if="isIngesting" class="spinner" />
        <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon">
          <polyline points="1 4 1 10 7 10" />
          <path d="M3.51 15a9 9 0 1 0 .49-3.08" />
        </svg>
        <span>{{ isIngesting ? "Carregando feeds..." : "Atualizar Notícias" }}</span>
      </button>

      <p v-if="ingestMessage" class="ingest-message" :class="ingestSuccess ? 'success' : 'error'">
        {{ ingestMessage }}
      </p>
    </div>

    <!-- Footer -->
    <div class="sidebar-footer">
      <span class="sidebar-footer-text">Projeto de Faculdade · IA Generativa</span>
    </div>
  </aside>
</template>

<script setup>
import { ref } from "vue";
import axios from "axios";

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["quick-question"]);

const quickQuestions = [
  { id: 1, text: "Qual é a notícia mais recente?" },
  { id: 2, text: "Resumo de tecnologia hoje" },
  { id: 3, text: "O que aconteceu no mundo?" },
  { id: 4, text: "Quais são as novidades de negócios?" },
  { id: 5, text: "Novidades de ciência e meio ambiente" },
];

const bbcFeeds = [
  { label: "BBC News — Geral" },
  { label: "BBC News — Mundo" },
  { label: "BBC News — Tecnologia" },
  { label: "BBC News — Negócios" },
  { label: "BBC News — Ciência & Ambiente" },
];

const isIngesting = ref(false);
const ingestMessage = ref("");
const ingestSuccess = ref(false);

async function handleIngest() {
  isIngesting.value = true;
  ingestMessage.value = "";

  try {
    const { data } = await axios.post("/ingest");
    ingestSuccess.value = true;
    ingestMessage.value = `✅ ${data.chunks_stored} chunks de ${data.articles_processed} artigos salvos!`;
  } catch (err) {
    ingestSuccess.value = false;
    ingestMessage.value =
      "❌ " + (err.response?.data?.detail || "Erro ao ingerir feeds.");
  } finally {
    isIngesting.value = false;
  }
}
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 280px;
  min-width: 280px;
  height: 100%;
  background: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border);
  padding: 1.5rem 1rem;
  gap: 1.5rem;
  overflow-y: auto;
}

/* Brand */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--color-border);
}
.brand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: var(--color-accent);
  border-radius: 8px;
  color: white;
}
.brand-icon svg {
  width: 20px;
  height: 20px;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}
.brand-sub {
  font-size: 0.7rem;
  color: var(--color-accent-light);
  font-weight: 500;
}

/* Sections */
.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.sidebar-section-title {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
  margin: 0;
}

/* Quick questions */
.quick-questions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.quick-btn {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text-secondary);
  font-size: 0.8rem;
  font-family: "Inter", sans-serif;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
}
.quick-btn:hover:not(:disabled) {
  background: var(--color-accent-glow);
  border-color: var(--color-accent);
  color: var(--color-text-primary);
  transform: translateX(2px);
}
.quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.quick-btn-text {
  line-height: 1.3;
}

/* Feeds list */
.feeds-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.25rem;
}
.feed-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}
.feed-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent-light);
  flex-shrink: 0;
}

/* Ingest button */
.ingest-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.6rem;
  background: var(--color-accent);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 0.82rem;
  font-weight: 600;
  font-family: "Inter", sans-serif;
  cursor: pointer;
  transition: opacity 0.2s ease;
}
.ingest-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.ingest-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
.btn-icon {
  width: 14px;
  height: 14px;
}
.ingest-message {
  font-size: 0.75rem;
  margin: 0;
  padding: 0.4rem 0.5rem;
  border-radius: 6px;
}
.ingest-message.success {
  background: rgba(34, 197, 94, 0.1);
  color: #4ade80;
}
.ingest-message.error {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
}

/* Spinner */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Footer */
.sidebar-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
}
.sidebar-footer-text {
  font-size: 0.68rem;
  color: var(--color-text-muted);
}
</style>
