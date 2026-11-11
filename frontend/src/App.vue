<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { createClient } from '@supabase/supabase-js'
import axios from 'axios'
import AuthForm from './components/AuthForm.vue'
import ChatMessage from './components/ChatMessage.vue'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '', timeout: 15000 })
const client = shallowRef(null)
const session = shallowRef(null)
const initializing = ref(true)
const authError = ref('')
let authSubscription
let accountRequests = new AbortController()

const news = ref([])
const sidebarOpen = ref(false)
const pageSize = ref(5)
const newsLoading = ref(false)
const newsError = ref('')
const publishers = ['BBC News', 'Agência Brasil']
const categories = ['Mundo', 'Economia', 'Tecnologia', 'Ciência e ambiente', 'Política',
  'Saúde', 'Educação', 'Esportes', 'Cultura', 'Justiça', 'Direitos humanos', 'Geral']
const preferredTopics = ref([])
const source = ref('')
const savingPreferences = ref(false)
const preferenceStatus = ref('')
const preferenceError = ref(false)
const filteredNews = computed(() => {
  const available = news.value.filter((article) => !source.value || source.value === article.publisher)
  const preferred = []
  const other = []
  for (const article of available) {
    (preferredTopics.value.includes(article.category) ? preferred : other).push(article)
  }
  return [...preferred, ...other]
})
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
  sidebarOpen.value = false
  pageSize.value = 5
  newsError.value = ''
  newsLoading.value = false
  syncing.value = false
  syncStatus.value = ''
  chatLoading.value = false
  resetChat()
  savingPreferences.value = false
  preferenceStatus.value = ''
  if (userId) loadNews()
})

watch([() => session.value?.user.id, () => session.value?.user.user_metadata?.news_preferences], ([, preferences]) => {
  preferredTopics.value = categories.filter((topic) =>
    Array.isArray(preferences?.topics) && preferences.topics.includes(topic))
  source.value = publishers.includes(preferences?.source) ? preferences.source : ''
}, { immediate: true })

watch([source, preferredTopics], () => {
  pageSize.value = 5
  preferenceStatus.value = ''
})

async function savePreferences() {
  savingPreferences.value = true
  preferenceStatus.value = ''
  preferenceError.value = false
  const signal = accountRequests.signal
  try {
    const { error } = await client.value.auth.updateUser({
      data: { news_preferences: { topics: preferredTopics.value, source: source.value } },
    })
    if (error) throw error
    if (!signal.aborted) preferenceStatus.value = 'Preferências salvas.'
  } catch {
    if (!signal.aborted) {
      preferenceError.value = true
      preferenceStatus.value = 'Não foi possível salvar. Tente novamente.'
    }
  } finally {
    if (!signal.aborted) savingPreferences.value = false
  }
}

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
  } catch (error) {
    if (!signal.aborted) newsError.value = detail(error, 'Não foi possível carregar as manchetes.')
  } finally {
    if (!signal.aborted) newsLoading.value = false
  }
}

async function openArticle(article) {
  if (chatLoading.value) return
  selectedArticle.value = article
  sidebarOpen.value = false
  chatError.value = ''
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
  const history = messages.value.slice(-6).map(({ role, content }) => ({ role, content: content.slice(0, 2000) }))
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
      data: { question: trimmed, article_url: article?.url, history },
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

  <div v-else class="workspace" @keydown.esc="sidebarOpen = false">
    <button v-if="sidebarOpen" class="sidebar-scrim" aria-label="Fechar notícias" @click="sidebarOpen = false" />
    <aside id="news-sidebar" class="navigation" :class="{ 'sidebar-open': sidebarOpen }" aria-label="Painel de notícias">
      <div class="sidebar-heading">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">R</span>
          <span>RAG News</span>
        </div>
        <button class="text-button mobile-control" @click="sidebarOpen = false">Fechar</button>
      </div>

      <div class="sidebar-scroll">
        <section class="sidebar-settings" aria-label="Preferências de notícias">
          <label class="source-label" for="news-source">Fontes das manchetes</label>
          <select id="news-source" v-model="source" :disabled="savingPreferences">
            <option value="">Todas as fontes</option>
            <option v-for="publisher in publishers" :key="publisher">{{ publisher }}</option>
          </select>
          <details class="topic-settings">
            <summary>Meus temas <span v-if="preferredTopics.length">({{ preferredTopics.length }})</span></summary>
            <fieldset :disabled="savingPreferences" class="topic-options">
              <legend>Os temas escolhidos aparecem primeiro.</legend>
              <label v-for="topic in categories" :key="topic">
                <input v-model="preferredTopics" type="checkbox" :value="topic" /> {{ topic }}
              </label>
            </fieldset>
          </details>
          <button class="text-button" :disabled="savingPreferences" @click="savePreferences">
            {{ savingPreferences ? 'Salvando…' : 'Salvar preferências' }}
          </button>
          <p v-if="preferenceStatus" :class="{ error: preferenceError }" role="status">{{ preferenceStatus }}</p>
        </section>

        <section class="headlines" aria-labelledby="headlines-heading">
          <div class="headlines-heading">
            <h2 id="headlines-heading">{{ preferredTopics.length ? 'Para você' : 'Principais notícias' }}</h2>
            <button class="text-button" :disabled="newsLoading" @click="loadNews">Atualizar</button>
          </div>
          <p v-if="newsError" class="error" role="alert">{{ newsError }}</p>
          <p v-else-if="newsLoading && !news.length" class="muted" role="status">Buscando notícias…</p>
          <p v-else-if="!visibleNews.length" class="muted">Nenhuma manchete disponível para esta fonte.</p>
          <ul class="headline-list">
            <li v-for="article in visibleNews" :key="article.url" :class="{ 'headline-active': selectedArticle?.url === article.url }">
              <button class="headline-title" :disabled="chatLoading" :aria-pressed="selectedArticle?.url === article.url"
                @click="openArticle(article)">{{ article.title }}</button>
              <div class="headline-meta">
                <span>{{ article.category }}</span>
                <a :href="article.url" target="_blank" rel="noopener noreferrer"
                  :aria-label="'Ler em ' + article.publisher + ': ' + article.title">{{ article.publisher }} ↗</a>
              </div>
            </li>
          </ul>
          <button v-if="filteredNews.length > pageSize" class="text-button more-news" @click="pageSize += 5">
            Mostrar mais notícias
          </button>
        </section>
      </div>

      <div class="account">
        <p class="account-email" :title="session.user.email">{{ session.user.email }}</p>
        <div class="account-actions">
          <button class="text-button" @click="dark = !dark">{{ dark ? 'Tema claro' : 'Tema escuro' }}</button>
          <button class="text-button" @click="signOut">Sair</button>
        </div>
        <p v-if="authError" class="error" role="alert">{{ authError }}</p>
      </div>
    </aside>

    <main class="chat-page">
      <header class="chat-header">
        <div class="chat-header-title">
          <button class="secondary-button mobile-control" aria-controls="news-sidebar" :aria-expanded="sidebarOpen"
            @click="sidebarOpen = !sidebarOpen">Notícias</button>
          <h1>Chat com notícias</h1>
        </div>
        <button class="secondary-button" :disabled="chatLoading" @click="resetChat">+ Nova conversa</button>
      </header>

      <div ref="messageList" class="conversation" aria-label="Conversa" role="log">
        <div v-if="!messages.length" class="chat-empty">
          <span class="brand-mark welcome-mark" aria-hidden="true">R</span>
          <h2>{{ selectedArticle ? 'Vamos falar sobre esta notícia?' : 'O que está acontecendo?' }}</h2>
          <p class="muted">{{ selectedArticle ? selectedArticle.title : 'Pergunte sobre o noticiário ou escolha uma manchete na lateral.' }}</p>
          <button v-if="selectedArticle" class="secondary-button" @click="sendQuestion('Resuma esta matéria em português.')">
            Resumir esta matéria
          </button>
          <button v-else class="secondary-button" @click="sendQuestion('Quais são os destaques do noticiário recente?')">
            Quais são os destaques?
          </button>
        </div>
        <div v-else class="conversation-messages">
          <ChatMessage v-for="message in messages" :key="message.id" :message="message" />
        </div>
      </div>

      <div class="composer-area">
        <div v-if="selectedArticle" class="selected-article">
          <div>
            <p class="muted">{{ selectedArticle.publisher }} · Matéria em foco</p>
            <a :href="selectedArticle.url" target="_blank" rel="noopener noreferrer">{{ selectedArticle.title }} ↗</a>
          </div>
          <button class="text-button" :disabled="chatLoading" @click="selectedArticle = null">Remover</button>
        </div>
        <p v-if="chatError" class="notice error" role="alert">{{ chatError }}</p>
        <form class="composer" @submit.prevent="sendQuestion(question)">
          <textarea ref="input" v-model="question" rows="2" maxlength="2000" aria-label="Sua pergunta"
            placeholder="Pergunte sobre as notícias…" @keydown.enter="handleEnter" />
          <button class="primary-button" :disabled="chatLoading || !question.trim()" type="submit">
            {{ chatLoading ? 'Enviando…' : 'Enviar' }}
          </button>
        </form>
        <div class="index-tools">
          <button class="text-button" :disabled="syncing" @click="syncIndex">
            {{ syncing ? 'Atualizando índice…' : 'Atualizar índice de busca' }}
          </button>
          <span v-if="syncStatus" :class="{ error: syncFailed }" role="status">{{ syncStatus }}</span>
        </div>
      </div>
    </main>
  </div>
</template>
