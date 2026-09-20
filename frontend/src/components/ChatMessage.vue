<template>
  <div class="message-wrapper" :class="message.role">
    <!-- Avatar -->
    <div class="avatar" :class="message.role">
      <span v-if="message.role === 'user'">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-5.33 0-8 2.67-8 4v1h16v-1c0-1.33-2.67-4-8-4Z"/>
        </svg>
      </span>
      <span v-else>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
      </span>
    </div>

    <!-- Bubble -->
    <div class="bubble-wrapper">
      <div class="bubble" :class="message.role">
        <!-- Typing indicator for loading AI messages -->
        <div v-if="message.isLoading" class="typing-dots">
          <span /><span /><span />
        </div>
        <p v-else class="bubble-text">{{ message.content }}</p>
      </div>

      <!-- Sources -->
      <div v-if="message.sources && message.sources.length" class="sources">
        <span class="sources-label">Fontes:</span>
        <a
          v-for="src in message.sources"
          :key="src"
          :href="src"
          target="_blank"
          rel="noopener noreferrer"
          class="source-link"
        >
          {{ formatSource(src) }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
    // shape: { id, role: 'user'|'assistant', content, sources?, isLoading? }
  },
});

function formatSource(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
</script>

<style scoped>
.message-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  max-width: 820px;
  width: 100%;
  animation: fadeSlideIn 0.25s ease forwards;
}
.message-wrapper.user {
  flex-direction: row-reverse;
  align-self: flex-end;
}
.message-wrapper.assistant {
  align-self: flex-start;
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Avatar */
.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex-shrink: 0;
  color: white;
}
.avatar.user {
  background: linear-gradient(135deg, #7c3aed, #4f46e5);
}
.avatar.assistant {
  background: linear-gradient(135deg, #0f766e, #0891b2);
}
.avatar svg {
  width: 18px;
  height: 18px;
}

/* Bubble */
.bubble-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-width: calc(100% - 50px);
}
.bubble {
  padding: 0.75rem 1rem;
  border-radius: 14px;
  font-size: 0.875rem;
  line-height: 1.65;
}
.bubble.user {
  background: var(--color-user-bubble);
  border: 1px solid rgba(124, 58, 237, 0.3);
  border-bottom-right-radius: 4px;
  color: var(--color-text-primary);
}
.bubble.assistant {
  background: var(--color-ai-bubble);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px;
  color: var(--color-text-primary);
}
.bubble-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Typing dots */
.typing-dots {
  display: flex;
  gap: 5px;
  padding: 4px 2px;
}
.typing-dots span {
  width: 8px;
  height: 8px;
  background: var(--color-accent-light);
  border-radius: 50%;
  animation: bounce 1.2s infinite ease-in-out;
}
.typing-dots span:nth-child(1) {
  animation-delay: 0s;
}
.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes bounce {
  0%, 80%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  40% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

/* Sources */
.sources {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}
.sources-label {
  font-size: 0.7rem;
  color: var(--color-text-muted);
}
.source-link {
  font-size: 0.7rem;
  color: var(--color-accent-light);
  text-decoration: none;
  padding: 1px 6px;
  background: var(--color-accent-glow);
  border-radius: 4px;
  transition: opacity 0.15s;
}
.source-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}
</style>
