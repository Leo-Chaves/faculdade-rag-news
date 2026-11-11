<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { createClient } from '@supabase/supabase-js'
import axios from 'axios'
import AuthForm from './components/AuthForm.vue'
import ChatMessage from './components/ChatMessage.vue'
import NewsCard from './components/NewsCard.vue'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '', timeout: 15000 })
const client = shallowRef(null)
const session = shallowRef(null)
const initializing = ref(true)
const authError = ref('')
let authSubscription
let accountRequests = new AbortController()

const view = ref('news')
const news = ref([])
const category = ref('')
const pageSize = ref(7)
const newsLoading = ref(false)
const newsError = ref('')
const categories = computed(() => [...new Set(news.value.map((article) => article.category))])
const filteredNews = computed(() =>
  category.value ? news.value.filter((article) => article.category === category.value) : news.value,
)
const visibleNews = computed(() => filteredNews.value.slice(0, pageSize.value))

const messages = ref([])
const question = ref('')
const selectedArticle = ref(null)
const chatLoading = ref(false)
const chatError = ref('')
const input = ref(null)
const messageList = ref(null)
let nextMessageId = 0

const syncing = ref(false)
const syncStatus = ref('')
const syncFailed = ref(false)
const dark = ref(localStorage.getItem('theme') === 'dark')

watch(dark, (value) => {
  document.documentElement.classList.toggle('dark', value)
  localStorage.setItem('theme', value ? 'dark' : 'light')
}, { immediate: true })

function detail(error, fallback) {
  const message = error.response?.data?.detail
  return typeof message === 'string' ? message : fallback
}

async function request(config) {
  const signal = accountRequests.signal
  const { data } = await client.value.auth.getSession()
  signal.throwIfAborted()
  if (!data.session) throw new Error('Sessão encerrada.')
  const response = await api.request({
    ...config,
    signal,
    headers: { Authorization: `Bearer ${data.session.access_token}` },
  })
  return response.data
}

async function initialize() {
  initializing.value = true
  authError.value = ''
  try {
    const { data } = await api.get('/auth/config')
    client.value = createClient(data.url, data.key)
    const { data: listener } = client.value.auth.onAuthStateChange((_event, currentSession) => {
      session.value = currentSession
      initializing.value = false
    })
    authSubscription = listener.subscription
  } catch (error) {
    authError.value = detail(error, 'Não foi possível conectar ao serviço de login.')
    initializing.value = false
  }
}

onMounted(initialize)
onUnmounted(() => {
  authSubscription?.unsubscribe()
  accountRequests.abort()
})

watch(() => session.value?.user.id, (userId) => {
  accountRequests.abort()
  accountRequests = new AbortController()
  news.value = []
  category.value = ''
  pageSize.value = 7
  newsError.value = ''
  newsLoading.value = false
  syncing.value = false
  syncStatus.value = ''
  chatLoading.value = false
  resetChat()
  view.value = 'news'
  if (userId) loadNews()
})

async function signOut() {
  authError.value = ''
  const { error } = await client.value.auth.signOut({ scope: 'local' })
  if (error) authError.value = 'Não foi possível sair. Tente novamente.'
}

async function loadNews() {
  const signal = accountRequests.signal
  newsLoading.value = true
  newsError.value = ''
  try {
    const articles = await request({ url: '/news' })
    if (signal.aborted) return
    news.value = articles
    if (!categories.value.includes(category.value)) category.value = ''
  } catch (error) {
    if (!signal.aborted) newsError.value = detail(error, 'Não foi possível carregar as manchetes.')
  } finally {
    if (!signal.aborted) newsLoading.value = false
  }
}

function filterNews(topic) {
  category.value = topic
  pageSize.value = 7
}

async function openArticle(article) {
  if (chatLoading.value) return
  if (selectedArticle.value?.url !== article.url) resetChat()
  selectedArticle.value = article
  view.value = 'chat'
  await nextTick()
  input.value?.focus()
}

function resetChat() {
  messages.value = []
  selectedArticle.value = null
  question.value = ''
  chatError.value = ''
}

async function scrollChat() {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}

async function sendQuestion(text) {
  const trimmed = text.trim()
  if (!trimmed || chatLoading.value) return

  const signal = accountRequests.signal
  const article = selectedArticle.value
  chatLoading.value = true
  chatError.value = ''
  question.value = ''
  const userMessageId = ++nextMessageId
  messages.value.push({ id: userMessageId, role: 'user', content: trimmed })
  const id = ++nextMessageId
  messages.value.push({ id, role: 'assistant', isLoading: true })
  scrollChat()

  try {
    const data = await request({
      url: '/chat',
      method: 'POST',
      timeout: 120000,
      data: { question: trimmed, article_url: article?.url },
    })
    if (signal.aborted) return
    messages.value = messages.value.map((message) => message.id === id
      ? { id, role: 'assistant', content: data.answer, articles: data.articles, sources: data.sources }
      : message)
  } catch (error) {
    if (signal.aborted) return
    messages.value = messages.value.filter((message) => message.id !== id && message.id !== userMessageId)
    question.value = trimmed
    chatError.value = detail(error, 'Não foi possível obter a resposta. Tente novamente.')
  } finally {
    if (!signal.aborted) {
      chatLoading.value = false
      await scrollChat()
      input.value?.focus()
    }
  }
}

async function syncIndex() {
  const signal = accountRequests.signal
  syncing.value = true
  syncStatus.value = ''
  syncFailed.value = false
  try {
    const result = await request({ url: '/ingest', method: 'POST', timeout: 120000 })
    if (signal.aborted) return
    syncStatus.value = result.articles_processed
      ? `${result.articles_processed} matérias adicionadas ao índice.`
      : 'O índice já contém as matérias atuais.'
  } catch (error) {
    if (signal.aborted) return
    syncFailed.value = true
    syncStatus.value = detail(error, 'Não foi possível atualizar o índice.')
  } finally {
    if (!signal.aborted) syncing.value = false
  }
}

function handleEnter(event) {
  if (event.shiftKey || event.isComposing) return
  event.preventDefault()
  sendQuestion(question.value)
}
</script>

<template>
  <main v-if="initializing || !session" class="auth-page">
    <div class="auth-brand">
      <span class="brand-mark" aria-hidden="true">R</span>
      <span>RAG News</span>
    </div>
    <section class="auth-panel" aria-label="Acesso ao RAG News">
      <p v-if="initializing" role="status">Carregando…</p>
      <template v-else-if="authError">
        <h1>Entre na sua conta</h1>
        <p class="notice error" role="alert">{{ authError }}</p>
        <button class="primary-button" @click="initialize">Tentar novamente</button>
      </template>
      <AuthForm v-else :client="client" />
    </section>
  </main>

  <div v-else class="workspace">
    <aside class="navigation">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">R</span>
        <span>RAG News</span>
      </div>
      <nav aria-label="Navegação principal">
        <button :aria-current="view === 'news' ? 'page' : undefined" @click="view = 'news'">Manchetes</button>
        <button :aria-current="view === 'chat' ? 'page' : undefined" @click="view = 'chat'">Chat</button>
      </nav>
      <div class="account">
        <p class="account-email" :title="session.user.email">{{ session.user.email }}</p>
        <div class="account-actions">
          <button class="text-button" @click="dark = !dark">{{ dark ? 'Tema claro' : 'Tema escuro' }}</button>
          <button class="text-button" @click="signOut">Sair</button>
        </div>
        <p v-if="authError" class="error" role="alert">{{ authError }}</p>
      </div>
    </aside>

    <main v-if="view === 'news'" class="main-content">
      <header class="page-header">
        <div>
          <h1>Últimas da BBC</h1>
          <p class="muted">Escolha uma manchete para ler ou conversar sobre ela.</p>
        </div>
        <button class="secondary-button" :disabled="newsLoading" @click="loadNews">
          {{ newsLoading ? 'Atualizando…' : 'Atualizar manchetes' }}
        </button>
      </header>
      <p v-if="newsError" class="notice error" role="alert">{{ newsError }}</p>
      <p v-else-if="newsLoading && !news.length" class="notice" role="status">Buscando manchetes da BBC…</p>
      <p v-else-if="!news.length" class="notice">Nenhuma manchete disponível.</p>
      <template v-if="news.length">
        <div class="topic-filters" aria-label="Filtrar manchetes por tema">
          <button :aria-pressed="!category" @click="filterNews('')">Todas</button>
          <button v-for="topic in categories" :key="topic" :aria-pressed="category === topic"
            @click="filterNews(topic)">{{ topic }}</button>
        </div>
        <div class="news-grid">
          <NewsCard v-for="(article, index) in visibleNews" :key="article.url" :article="article"
            :featured="index === 0" :chat-busy="chatLoading" @ask="openArticle" />
        </div>
        <button v-if="filteredNews.length > pageSize" class="secondary-button more-news"
          @click="pageSize += 6">Mostrar mais notícias</button>
      </template>
    </main>

    <main v-else class="main-content chat-page">
      <header class="page-header">
        <div>
          <h1>Chat com notícias</h1>
          <p class="muted">Faça uma pergunta sobre as matérias da BBC.</p>
        </div>
        <button class="secondary-button" :disabled="chatLoading" @click="resetChat">Nova conversa</button>
      </header>

      <div v-if="selectedArticle" class="selected-article">
        <div>
          <p class="muted">Matéria em foco</p>
          <a :href="selectedArticle.url" target="_blank" rel="noopener noreferrer">{{ selectedArticle.title }} ↗</a>
        </div>
        <button class="text-button" :disabled="chatLoading" @click="selectedArticle = null">Remover</button>
      </div>
      <div v-else class="index-tools">
        <button class="text-button" :disabled="syncing" @click="syncIndex">
          {{ syncing ? 'Atualizando índice…' : 'Atualizar índice de busca' }}
        </button>
        <span v-if="syncStatus" :class="{ error: syncFailed }" role="status">{{ syncStatus }}</span>
      </div>

      <section ref="messageList" class="conversation" aria-label="Conversa" role="log">
        <ChatMessage v-for="message in messages" :key="message.id" :message="message" />
        <div v-if="!messages.length" class="chat-empty">
          <p>{{ selectedArticle ? 'Quer entender melhor esta matéria?' : 'O que você quer descobrir?' }}</p>
          <button v-if="selectedArticle" class="secondary-button" @click="sendQuestion('Resuma esta matéria em português.')">
            Resumir esta matéria
          </button>
          <button v-else class="secondary-button" @click="view = 'news'">Escolher uma manchete</button>
        </div>
      </section>

      <p v-if="chatError" class="notice error" role="alert">{{ chatError }}</p>
      <form class="composer" @submit.prevent="sendQuestion(question)">
        <textarea ref="input" v-model="question" rows="2" maxlength="2000" aria-label="Sua pergunta"
          placeholder="Escreva sua pergunta…" @keydown.enter="handleEnter" />
        <button class="primary-button" :disabled="chatLoading || !question.trim()" type="submit">
          {{ chatLoading ? 'Enviando…' : 'Enviar' }}
        </button>
      </form>
    </main>
  </div>
</template>
